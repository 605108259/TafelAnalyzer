from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, BUTTON_STYLE, LIST_STYLE, PANEL_STYLE,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, BG_HOVER, BG_CARD,
)


class FileListItem(QWidget):
    """Custom widget for each file row: name | badge | remove button."""

    remove_clicked = Signal(object)  # Path

    def __init__(self, file_path: Path, is_processed: bool = False):
        super().__init__()
        self.file_path = file_path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.name_label = QLabel(file_path.name)
        self.name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)

        if is_processed:
            badge = QLabel("✓")
            badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 12px;")
            layout.addWidget(badge)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 12px; color: #dc2626; font-size: 14px; }}"
            f"QPushButton:hover {{ background: #fee2e2; }}"
        )
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.file_path))
        layout.addWidget(remove_btn)


class FilePanel(QWidget):
    """Side panel for file selection and management."""

    file_selected = Signal(object)   # Path
    file_removed = Signal(object)    # Path
    files_loaded = Signal(list)      # list[Path]
    cache_import_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel("📂 文件")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Select button
        self.btn_select = QPushButton("📁 选择数据文件…")
        self.btn_select.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.clicked.connect(self._on_select)
        layout.addWidget(self.btn_select)

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_STYLE)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.file_list, stretch=1)

        # Cache import
        self.btn_cache = QPushButton("📥 导入缓存")
        self.btn_cache.setStyleSheet(BUTTON_STYLE)
        self.btn_cache.setCursor(Qt.PointingHandCursor)
        self.btn_cache.clicked.connect(self.cache_import_requested.emit)
        layout.addWidget(self.btn_cache)

        # Info
        self.info_label = QLabel("等待选择数据文件 …")
        self.info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Internal state
        self._file_paths: list[Path] = []
        self._processed: set[str] = set()  # str(file_path) -> processed

    def _on_select(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择数据文件", "",
            "支持的文件 (*.tdms *.txt *.csv *.xlsx *.xls *.cor);;All files (*.*)"
        )
        if not paths:
            return
        selected = []
        for p_str in paths:
            path = Path(p_str)
            if path not in self._file_paths:
                self._file_paths.append(path)
                selected.append(path)
        self._rebuild_list()
        if selected:
            self.files_loaded.emit(selected)

    def _rebuild_list(self) -> None:
        self.file_list.clear()
        for path in self._file_paths:
            item = QListWidgetItem()
            widget = FileListItem(path, str(path) in self._processed)
            widget.remove_clicked.connect(self._on_remove)
            item.setSizeHint(widget.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, widget)

    def _on_remove(self, path: Path) -> None:
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{path.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._file_paths.remove(path)
        self._processed.discard(str(path))
        self._rebuild_list()
        self.file_removed.emit(path)

    def _on_item_double_click(self, item: QListWidgetItem) -> None:
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            self.file_selected.emit(widget.file_path)

    def set_processed(self, path: Path) -> None:
        self._processed.add(str(path))
        self._rebuild_list()

    def set_file_paths(self, paths: list[Path], preferred: Path | None = None) -> None:
        self._file_paths = list(paths)
        self._rebuild_list()

    def update_info(self, text: str) -> None:
        self.info_label.setText(text)
