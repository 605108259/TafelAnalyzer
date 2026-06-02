from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui.theme import (
    ACCENT,
    ACCENT_BUTTON_STYLE,
    BG_CARD,
    BG_HOVER,
    BORDER,
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class HistoryWorkspace(QWidget):
    restore_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD};")
        self._cache_path = ""
        self._entry_id = ""
        self._can_restore = False
        self._payload_cache: dict[str, tuple[tuple[int, int] | None, dict[str, Any], str]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        self.title_label = QLabel("历史项目预览")
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {TEXT_PRIMARY};")
        title_col.addWidget(self.title_label)
        self.subtitle_label = QLabel("选择左侧项目查看详情")
        self.subtitle_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        title_col.addWidget(self.subtitle_label)
        header.addLayout(title_col, stretch=1)

        self.restore_button = QPushButton("恢复此项目")
        self.restore_button.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_button.clicked.connect(self._restore_current)
        header.addWidget(self.restore_button)
        root.addLayout(header)

        self.status_label = QLabel()
        self.status_label.setFixedHeight(28)
        root.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(
            f"QProgressBar {{ border: none; background: {BG_HOVER}; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}"
        )
        self.progress.hide()
        root.addWidget(self.progress)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._build_files_panel(), stretch=1)
        top.addWidget(self._build_comparison_panel(), stretch=1)
        root.addLayout(top, stretch=1)

        details_title = QLabel("分析设置")
        details_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT_PRIMARY};")
        root.addWidget(details_title)

        self.details_browser = QTextBrowser()
        self.details_browser.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid {BORDER}; border-radius: 8px; "
            f"background: {BG_HOVER}; color: {TEXT_PRIMARY}; font-size: 12px; padding: 8px; }}"
        )
        self.details_browser.setFixedHeight(170)
        root.addWidget(self.details_browser)

        self.set_entry(None)

    def _build_files_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self.files_title = QLabel("数据文件（0）")
        self.files_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(self.files_title)
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.files_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.files_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            f"QListWidget::item {{ border-bottom: 1px solid {BORDER}; padding: 6px 2px; }}"
            f"QListWidget::item:selected {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
        )
        layout.addWidget(self.files_list, stretch=1)
        return panel

    def _build_comparison_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self.comparison_title = QLabel("对比文件（0）")
        self.comparison_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(self.comparison_title)
        self.comparison_list = QListWidget()
        self.comparison_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.comparison_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.comparison_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            f"QListWidget::item {{ border-bottom: 1px solid {BORDER}; padding: 6px 2px; }}"
            f"QListWidget::item:selected {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
        )
        layout.addWidget(self.comparison_list, stretch=1)
        return panel

    def _panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ border: 1px solid {BORDER}; border-radius: 8px; background: {BG_CARD}; }}"
        )
        return panel

    def set_entry(self, entry: dict[str, Any] | None) -> None:
        if entry is None:
            self._cache_path = ""
            self._entry_id = ""
            self._can_restore = False
            self.title_label.setText("历史项目预览")
            self.subtitle_label.setText("选择左侧项目查看详情")
            self._set_status("没有选中的历史项目", TEXT_SECONDARY, enabled=False)
            self.files_list.clear()
            self.comparison_list.clear()
            self.files_title.setText("数据文件（0）")
            self.comparison_title.setText("对比文件（0）")
            self.details_browser.setPlainText("")
            self.restore_button.setEnabled(False)
            self.set_busy(False)
            return

        self._entry_id = str(entry.get("id") or entry.get("cache_path") or "")
        self._cache_path = str(entry.get("cache_path") or "")
        self.title_label.setText(str(entry.get("title") or "未命名项目"))
        self.subtitle_label.setText(str(entry.get("updated_at") or ""))

        payload, cache_error = self._load_payload(self._cache_path)
        cache_path = Path(self._cache_path) if self._cache_path else None

        can_restore = bool(cache_path is not None and cache_path.exists() and not cache_error)
        self._can_restore = can_restore
        if can_restore:
            self._set_status("可恢复", SUCCESS, enabled=True)
        else:
            self._set_status(cache_error or "不可恢复", DANGER, enabled=False)
        self.restore_button.setEnabled(can_restore)

        selected_paths = [
            str(path)
            for path in payload.get("selected_paths", entry.get("files", []))
            if str(path).strip()
        ]
        current_path = str(payload.get("current_path") or (selected_paths[0] if selected_paths else ""))
        self._set_files(selected_paths)
        self._set_comparison_files(payload.get("comparison_items", []))
        self._set_details(payload, current_path)

    def _set_status(self, text: str, color: str, *, enabled: bool) -> None:
        bg = "#dcfce7" if enabled else "#f8fafc"
        border = color if enabled else BORDER
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; background-color: {bg}; border: 1px solid {border}; "
            "border-radius: 8px; padding: 5px 9px; font-size: 12px; font-weight: 700;"
        )

    def _set_files(self, files: list[str]) -> None:
        self.files_list.clear()
        self.files_title.setText(f"数据文件（{len(files)}）")
        if not files:
            self.files_list.addItem(QListWidgetItem("无数据文件"))
            return
        for path_text in files:
            path = Path(path_text)
            item = QListWidgetItem(f"{path.name}\n{path_text}")
            item.setToolTip(path_text)
            self.files_list.addItem(item)

    def _set_comparison_files(self, items: list[Any]) -> None:
        self.comparison_list.clear()
        names: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("label") or item.get("file_name") or "")
            if not name:
                file_path = str(item.get("file_path") or "")
                name = Path(file_path).name if file_path else ""
            segment_index = item.get("segment_index")
            if name and segment_index is not None and "第" not in name:
                try:
                    name = f"{name} - 第{int(segment_index) + 1}段"
                except (TypeError, ValueError):
                    pass
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        if not names:
            self.comparison_title.setText("对比文件（0）")
            self.comparison_list.addItem(QListWidgetItem("无对比文件"))
            return
        self.comparison_title.setText(f"对比文件（{len(names)}）")
        for name in names:
            self.comparison_list.addItem(QListWidgetItem(name))

    def _set_details(self, payload: dict[str, Any], current_path: str) -> None:
        if not payload:
            self.details_browser.setPlainText("")
            return

        file_ui_cache = payload.get("file_ui_cache", {})
        current_settings = file_ui_cache.get(current_path, {}) if isinstance(file_ui_cache, dict) else {}
        if not current_settings and isinstance(file_ui_cache, dict) and file_ui_cache:
            first_value = next(iter(file_ui_cache.values()))
            current_settings = first_value if isinstance(first_value, dict) else {}

        lines = [
            f"电位公式: {current_settings.get('potential_formula', '-')}",
            f"电流公式: {current_settings.get('current_formula', '-')}",
            f"Eeq: {current_settings.get('e_eq', '-')}",
            f"窗口点数: {current_settings.get('window_range', '-')}",
            f"eta 范围: {current_settings.get('eta_range', '-')}",
            f"log(j) 范围: {current_settings.get('logj_range', '-')}",
            f"最小 R2: {current_settings.get('min_r2', '-')}",
            f"优先策略: {current_settings.get('fit_priority', '-')}",
        ]
        self.details_browser.setPlainText("\n".join(lines))

    def _restore_current(self) -> None:
        self.request_restore(self._cache_path)

    def request_restore(self, cache_path: str) -> None:
        if not cache_path:
            return
        self.set_busy(True)
        # Let the UI update before starting the synchronous restore work
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        self.restore_requested.emit(cache_path)

    def set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.restore_button.setEnabled(not busy and self._can_restore)
        if busy:
            self._set_status("正在恢复项目…", ACCENT, enabled=True)
        elif self._cache_path:
            if self._can_restore:
                self._set_status("可恢复", SUCCESS, enabled=True)
            else:
                self._set_status("不可恢复", DANGER, enabled=False)

    def _load_payload(self, cache_path_text: str) -> tuple[dict[str, Any], str]:
        if not cache_path_text:
            return {}, "没有缓存文件路径"
        cache_path = Path(cache_path_text)
        if not cache_path.exists():
            return {}, "缓存文件不存在"
        manifest_path = cache_path / "manifest.json" if cache_path.is_dir() else None
        try:
            stat_target = manifest_path if manifest_path is not None and manifest_path.exists() else cache_path
            stat = stat_target.stat()
            signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            signature = None

        cached = self._payload_cache.get(cache_path_text)
        if cached is not None and cached[0] == signature:
            return cached[1], cached[2]

        try:
            if cache_path.is_dir():
                payload = self._load_v3_preview_payload(cache_path)
            else:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            result = (signature, payload if isinstance(payload, dict) else {}, "")
        except Exception as exc:
            result = (signature, {}, f"缓存文件无法读取: {exc}")
        self._payload_cache[cache_path_text] = result
        return result[1], result[2]

    def _load_v3_preview_payload(self, cache_dir: Path) -> dict[str, Any]:
        manifest_path = cache_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"历史项目目录缺少 manifest.json: {cache_dir}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        file_ui: dict[str, Any] = {}
        file_ui_path = cache_dir / "file_ui.json"
        if file_ui_path.exists():
            raw = json.loads(file_ui_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                file_ui = raw

        comparison_items: list[Any] = []
        comparison_path = cache_dir / "comparison.json"
        if comparison_path.exists():
            raw = json.loads(comparison_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                comparison_items = raw.get("items", [])

        return {
            "cache_format_version": manifest.get("cache_format_version", 3),
            "selected_paths": manifest.get("selected_paths", []),
            "current_path": manifest.get("current_path"),
            "chart_view_state": manifest.get("chart_view_state", {}),
            "file_ui_cache": file_ui,
            "comparison_items": comparison_items,
        }
