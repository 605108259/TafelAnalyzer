from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ui.controllers.base import BaseAppController
from ui.controllers.worker_utils import stop_worker

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


def _safe_file_stem(value: str, fallback: str) -> str:
    stem = "".join("-" if ch in '<>:"/\\|?*' else ch for ch in value).strip(" .")
    return stem or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path


class BatchExportWorker(QThread):
    """Background worker for batch exporting multiple files/segments."""

    finished = Signal(int, int, list, object)  # success_count, fail_count, failed_paths, cache_archive_path
    error = Signal(str)

    def __init__(self, result_cache: dict, current_result_keys: dict,
                 out_dir: Path, file_name_map: dict[str, str] | None = None,
                 axis_overrides: dict | None = None,
                 cache_archive_path: Path | None = None,
                 cache_archive_components: dict | None = None):
        super().__init__()
        self.result_cache = result_cache
        self.current_result_keys = current_result_keys
        self.out_dir = out_dir
        self.file_name_map = dict(file_name_map or {})
        self.axis_overrides = dict(axis_overrides or {})
        self.cache_archive_path = cache_archive_path
        self.cache_archive_components = dict(cache_archive_components or {})

    def run(self) -> None:
        from core.export import export_processed_txt, export_fit_npz, plot_tafel

        success = 0
        fail = 0
        failed: list[str] = []
        for path_key, cache_key in self.current_result_keys.items():
            entry = self.result_cache.get(cache_key)
            if entry is None:
                fail += 1
                failed.append(f"{Path(path_key).name} (无缓存)")
                continue
            prepared = entry.get("prepared")
            if prepared is None:
                fail += 1
                failed.append(f"{Path(path_key).name} (无数据)")
                continue
            fit = entry.get("fit")  # may be None — still exportable
            try:
                stem = Path(path_key).stem
                prefix = (self.file_name_map.get(path_key) or "").strip() or stem
                seg_idx = prepared.segment.index + 1
                base = self.out_dir / f"{prefix}_seg{seg_idx}"
                export_processed_txt(base.with_suffix(".txt"), prepared, fit)
                export_fit_npz(base.with_suffix(".npz"), prepared, fit)
                plot_tafel(base.with_suffix(".png"), prepared, fit,
                           axis_overrides=self.axis_overrides)
                success += 1
            except Exception as e:
                fail += 1
                failed.append(f"{Path(path_key).name} (异常: {e})")
        archive_written: Path | None = None
        if self.cache_archive_path is not None and self.cache_archive_components:
            try:
                from core.cache import write_v3_project_zip

                write_v3_project_zip(
                    self.cache_archive_path,
                    self.cache_archive_components["manifest"],
                    self.cache_archive_components["file_ui"],
                    self.cache_archive_components["result_index"],
                    self.cache_archive_components["comparison"],
                    self.cache_archive_components["prepared_blobs"],
                    self.cache_archive_components["fit_blobs"],
                )
                archive_written = self.cache_archive_path
            except Exception as e:
                fail += 1
                failed.append(f"cache archive ({e})")
        self.finished.emit(success, fail, failed, archive_written)


class ExportController(BaseAppController):
    """Handles single, batch, and comparison export."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._batch_worker: BatchExportWorker | None = None

    def export_current(self) -> None:
        app = self.app
        fit = app._app_state.get("fit")
        prepared = app._app_state.get("prepared")
        if fit is None or prepared is None:
            QMessageBox.warning(app, "提示", "请先运行拟合")
            return

        path = app._app_state.get("tdms_path")
        if path is None:
            return

        export_name = app.state.files.display_name(path)
        default_name = f"{export_name}_tafel.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出结果",
            str(path.parent / default_name),
            "Text (*.txt);;NumPy NPZ (*.npz);;PNG Image (*.png)",
        )
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".txt":
                from core.export import export_processed_txt
                export_processed_txt(Path(file_path), prepared, fit)
            elif ext == ".npz":
                from core.export import export_fit_npz
                export_fit_npz(Path(file_path), prepared, fit)
            elif ext == ".png":
                app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
            app.status_bar.setText(f"已导出: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.critical(app, "导出失败", str(exc))

    def run_batch(self) -> None:
        app = self.app
        cache = app._app_state.get("result_cache", {})
        keys = app._app_state.get("current_result_keys", {})
        if not cache or not keys:
            QMessageBox.warning(app, "提示", "没有可用的拟合结果")
            return

        dir_path = QFileDialog.getExistingDirectory(app, "选择导出目录")
        if not dir_path:
            return

        file_name_map = {
            str(p): app.state.files.display_name(p)
            for p in app._app_state.get("selected_paths", [])
        }
        cache_archive_path: Path | None = None
        cache_archive_components: dict | None = None
        try:
            if hasattr(app, "files"):
                app.files._cache_current_analysis_state()
            from core.cache import (
                build_v3_manifest, build_v3_file_ui, build_v3_result_index,
                build_v3_comparison, build_v3_blobs,
            )

            selected_paths = [Path(p) for p in app._app_state.get("selected_paths", [])]
            if len(selected_paths) == 1:
                base_name = app.state.files.display_name(selected_paths[0])
            else:
                base_name = "tafel_project"
            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
            safe_title = _safe_file_stem(f"{base_name}_cache_{timestamp}", "tafel_project_cache")
            prepared_blobs, fit_blobs = build_v3_blobs(app)
            cache_archive_path = _unique_path(Path(dir_path) / f"{safe_title}.zip")
            cache_archive_components = {
                "manifest": build_v3_manifest(app),
                "file_ui": build_v3_file_ui(app),
                "result_index": build_v3_result_index(app),
                "comparison": build_v3_comparison(app),
                "prepared_blobs": prepared_blobs,
                "fit_blobs": fit_blobs,
            }
        except Exception as exc:
            app.status_bar.setText(f"缓存文件准备失败，继续导出数据: {str(exc)[:80]}")

        # Clean up previous worker
        stop_worker(self._batch_worker)

        app.status_bar.setText("正在批量导出…")
        axis_overrides = app._app_state.get("axis_label_overrides", {})
        self._batch_worker = BatchExportWorker(
            cache, keys, Path(dir_path), file_name_map, axis_overrides,
            cache_archive_path, cache_archive_components,
        )
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(self._on_batch_error)
        self._batch_worker.start()

    def _on_batch_finished(self, success: int, fail: int, failed: list, cache_archive_path) -> None:
        msg = f"批量导出完成: {success} 成功, {fail} 失败"
        if cache_archive_path:
            msg += f"，缓存: {Path(cache_archive_path).name}"
        if failed:
            detail = "; ".join(failed[:5])
            if len(failed) > 5:
                detail += f" ...等{len(failed)}个"
            msg += f" ({detail})"
        self.app.status_bar.setText(msg)

    def _on_batch_error(self, msg: str) -> None:
        self.app.status_bar.setText(f"批量导出错误: {msg[:60]}")
