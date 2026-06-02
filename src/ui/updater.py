"""Non-blocking update checker and one-click installer flow."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QProcess, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from core.version import APP_VERSION, UPDATE_MANIFEST_URL, UpdateInfo, is_newer_version


class UpdateCheckWorker(QThread):
    update_available = Signal(object)
    no_update = Signal()
    error = Signal(str)

    def __init__(self, manifest_url: str = UPDATE_MANIFEST_URL, *, timeout: float = 5.0):
        super().__init__()
        self.manifest_url = manifest_url
        self.timeout = timeout

    def run(self) -> None:
        try:
            request = urllib.request.Request(
                self.manifest_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": f"TAFSQ/{APP_VERSION}",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest = str(payload.get("version") or "").strip()
            url = str(payload.get("url") or payload.get("download_url") or "").strip()
            if latest and url and is_newer_version(latest, APP_VERSION):
                self.update_available.emit(
                    UpdateInfo(
                        version=latest,
                        url=url,
                        filename=str(payload.get("filename") or ""),
                        notes=str(payload.get("notes") or ""),
                        sha256=str(payload.get("sha256") or ""),
                        size=int(payload.get("size") or 0),
                        mandatory=bool(payload.get("mandatory", False)),
                    )
                )
            else:
                self.no_update.emit()
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            self.error.emit(str(exc))


class UpdateDownloadWorker(QThread):
    progress = Signal(int, int)
    finished_path = Signal(object)
    error = Signal(str)

    def __init__(self, info: UpdateInfo, *, timeout: float = 20.0):
        super().__init__()
        self.info = info
        self.timeout = timeout
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            target = _download_target_path(self.info)
            request = urllib.request.Request(
                self.info.url,
                headers={"User-Agent": f"TAFSQ/{APP_VERSION}"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                total = int(response.headers.get("Content-Length") or self.info.size or 0)
                downloaded = 0
                with target.open("wb") as handle:
                    while True:
                        if self._cancelled:
                            target.unlink(missing_ok=True)
                            return
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
            if self.info.sha256:
                actual = _sha256_file(target)
                if actual.lower() != self.info.sha256.lower():
                    target.unlink(missing_ok=True)
                    raise ValueError("安装包校验失败，文件可能不完整或已被篡改。")
            self.finished_path.emit(target)
        except Exception as exc:
            self.error.emit(str(exc))


def schedule_update_check(app, *, delay_ms: int = 1200) -> None:
    QTimer.singleShot(delay_ms, lambda: check_for_updates(app, silent=True))


def check_for_updates(app, *, silent: bool = False) -> None:
    if getattr(app, "_update_worker", None) is not None and app._update_worker.isRunning():
        return
    worker = UpdateCheckWorker()
    app._update_worker = worker
    worker.update_available.connect(lambda info: _show_update_prompt(app, info))
    if not silent:
        worker.no_update.connect(lambda: app.status_bar.setText("当前已是最新版本"))
        worker.error.connect(lambda msg: app.status_bar.setText(f"检查更新失败: {msg[:80]}"))
    worker.finished.connect(lambda: setattr(app, "_update_worker", None))
    worker.start()


def _show_update_prompt(app, info: UpdateInfo) -> None:
    notes = f"\n\n更新说明：\n{info.notes}" if info.notes else ""
    digest = f"\n\nSHA256：{info.sha256}" if info.sha256 else ""
    mandatory = "\n\n此版本标记为必须更新。" if info.mandatory else ""
    message = (
        f"检测到新版本 {info.version}，当前版本为 {APP_VERSION}。"
        f"{notes}{digest}{mandatory}\n\n是否立即下载并安装？"
    )
    box = QMessageBox(app)
    box.setWindowTitle("发现新版本")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(message)
    update_button = box.addButton("立即更新", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is update_button:
        _download_and_install(app, info)


def _download_and_install(app, info: UpdateInfo) -> None:
    progress = QProgressDialog("正在下载更新...", "取消", 0, 100, app)
    progress.setWindowTitle("更新")
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.show()

    worker = UpdateDownloadWorker(info)
    app._update_download_worker = worker

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            progress.setValue(min(100, int(done * 100 / total)))
            progress.setLabelText(f"正在下载更新... {done / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB")
        else:
            progress.setRange(0, 0)
            progress.setLabelText(f"正在下载更新... {done / 1024 / 1024:.1f} MB")

    def on_error(message: str) -> None:
        progress.close()
        QMessageBox.critical(app, "更新失败", message)

    def on_finished(path: Path) -> None:
        progress.setValue(100)
        progress.setLabelText("下载完成，准备安装...")
        _install_and_restart(app, path)

    progress.canceled.connect(worker.cancel)
    worker.progress.connect(on_progress)
    worker.error.connect(on_error)
    worker.finished_path.connect(on_finished)
    worker.finished.connect(lambda: setattr(app, "_update_download_worker", None))
    worker.start()


def _install_and_restart(app, installer_path: Path) -> None:
    current_exe = Path(sys.executable).resolve()
    script = _write_update_script(installer_path.resolve(), current_exe, os.getpid())
    started = QProcess.startDetached("cmd.exe", ["/c", str(script)])
    if not started:
        QMessageBox.critical(app, "更新失败", "无法启动安装程序。")
        return
    app.status_bar.setText("正在退出并安装更新...")
    QApplication.quit()


def _download_target_path(info: UpdateInfo) -> Path:
    filename = info.filename.strip() or Path(urllib.parse.urlparse(info.url).path).name
    if not filename:
        filename = f"TAFSQ-{info.version}-setup.exe"
    safe_name = "".join(ch for ch in filename if ch not in '<>:"/\\|?*').strip()
    if not safe_name.lower().endswith(".exe"):
        safe_name += ".exe"
    target_dir = Path(tempfile.gettempdir()) / "TAFSQ-update"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / safe_name


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_update_script(installer_path: Path, current_exe: Path, current_pid: int) -> Path:
    script_path = Path(tempfile.gettempdir()) / "TAFSQ-update" / "run-update.cmd"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    installer = _batch_var_value(installer_path)
    exe = _batch_var_value(current_exe)
    script_path.write_text(
        "\n".join([
            "@echo off",
            "setlocal",
            "set \"LOG=%TEMP%\\TAFSQ-update\\run-update.log\"",
            f"set \"INSTALLER={installer}\"",
            f"set \"CURRENT_EXE={exe}\"",
            f"set \"CURRENT_PID={int(current_pid)}\"",
            "echo [%DATE% %TIME%] updater started > \"%LOG%\"",
            "echo installer=%INSTALLER% >> \"%LOG%\"",
            "echo current_exe=%CURRENT_EXE% >> \"%LOG%\"",
            "echo current_pid=%CURRENT_PID% >> \"%LOG%\"",
            ":wait_app_exit",
            "tasklist /FI \"PID eq %CURRENT_PID%\" 2>nul | findstr /C:\"%CURRENT_PID%\" >nul",
            "if %ERRORLEVEL% EQU 0 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait_app_exit",
            ")",
            "echo [%DATE% %TIME%] app exited; launching installer >> \"%LOG%\"",
            "start \"\" /wait \"%INSTALLER%\" /SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS",
            "set \"INSTALL_EXIT=%ERRORLEVEL%\"",
            "echo [%DATE% %TIME%] installer exit code=%INSTALL_EXIT% >> \"%LOG%\"",
            "if \"%INSTALL_EXIT%\"==\"0\" start \"\" \"%CURRENT_EXE%\"",
            "del \"%~f0\"",
            "",
        ]),
        encoding="utf-8",
    )
    return script_path


def _batch_var_value(path: Path) -> str:
    return str(path).replace('"', '""')
