from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QComboBox, QSplitter,
    QCheckBox, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    PANEL_STYLE, SMALL_BUTTON_STYLE, DANGER_BUTTON_STYLE,
    ACCENT_BUTTON_STYLE, INPUT_STYLE, LIST_STYLE, CHECKBOX_STYLE,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, ACCENT, BG_HOVER,
)


class FileListItem(QWidget):
    """Custom widget for each file row: name | ✓ badge | × remove."""

    remove_clicked = Signal(object)  # Path

    def __init__(self, file_path: Path, is_processed: bool = False):
        super().__init__()
        self.setObjectName("FileItem")
        self.file_path = file_path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        name = QLabel(file_path.name)
        name.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(name, stretch=1)

        if is_processed:
            badge = QLabel("✓")
            badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 12px;")
            layout.addWidget(badge)

        btn = QPushButton("×")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 11px; color: #dc2626; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #fee2e2; }}"
        )
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.remove_clicked.emit(self.file_path))
        layout.addWidget(btn)


class SegmentItemWidget(QWidget):
    """One row in segment list: ▶ active | ☑ checkbox | label | R² | 🎨 color."""

    activated = Signal(int)
    toggled = Signal(int, bool)
    color_clicked = Signal(int)

    def __init__(self, index: int, label: str, color: str,
                 is_active: bool, is_checked: bool, r2: float | None):
        super().__init__()
        self.setObjectName("SegmentItem")
        self.segment_index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Active indicator
        active_symbol = "▶" if is_active else "  "
        active_color = ACCENT if is_active else TEXT_SECONDARY
        self.active_label = QLabel(active_symbol)
        self.active_label.setStyleSheet(f"color: {active_color}; font-size: 10px;")
        self.active_label.setFixedWidth(16)
        layout.addWidget(self.active_label)

        # Checkbox
        self.cb = QCheckBox()
        self.cb.setChecked(is_checked)
        self.cb.setStyleSheet(CHECKBOX_STYLE)
        self.cb.stateChanged.connect(lambda state: self.toggled.emit(index, bool(state)))
        layout.addWidget(self.cb)

        # Label
        name = QLabel(label)
        name.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(name, stretch=1)

        # R² badge
        if r2 is not None:
            r2_label = QLabel(f"R²={r2:.4f}")
            r2_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
            layout.addWidget(r2_label)
        else:
            na = QLabel("未拟合")
            na.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            layout.addWidget(na)

        # Color swatch
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(index))
        layout.addWidget(self.color_btn)

        # Click on row body activates segment
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.activated.emit(self.segment_index)
        super().mousePressEvent(event)

    def update_state(self, is_active: bool, is_checked: bool, r2: float | None, color: str):
        self.active_label.setText("▶" if is_active else "  ")
        self.active_label.setStyleSheet(
            f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 10px;"
        )
        self.cb.blockSignals(True)
        self.cb.setChecked(is_checked)
        self.cb.blockSignals(False)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )


class FileSegmentPanel(QWidget):
    """Merged file selection + segment management panel with QSplitter."""

    # File signals
    files_selected = Signal(list)           # list[Path]
    file_activated = Signal(object)         # Path
    file_removed = Signal(object)           # Path
    cache_import_requested = Signal()
    export_name_changed = Signal(str)

    # Segment signals
    segment_activated = Signal(int)
    segment_toggled = Signal(int, bool)
    segment_color_changed = Signal(int, str)
    select_all_clicked = Signal()
    clear_all_clicked = Signal()
    add_to_comparison = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal()
    palette_manage_clicked = Signal()

    # Export signals
    export_current = Signal()
    export_batch = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ━━ File section (fixed height — outside splitter) ━━
        file_header = QWidget()
        file_header_layout = QVBoxLayout(file_header)
        file_header_layout.setContentsMargins(16, 12, 16, 4)
        file_header_layout.setSpacing(4)

        # Title row: count badge + icon buttons
        title_row = QHBoxLayout()
        self.file_count_label = QLabel("📂 文件 (0/0)")
        self.file_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        title_row.addWidget(self.file_count_label, stretch=1)

        btn_select = QPushButton("📁")
        btn_select.setToolTip("选择数据文件")
        btn_select.setFixedSize(28, 28)
        btn_select.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.clicked.connect(self._on_select_files)
        title_row.addWidget(btn_select)

        btn_cache = QPushButton("📥")
        btn_cache.setToolTip("导入缓存")
        btn_cache.setFixedSize(28, 28)
        btn_cache.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_cache.setCursor(Qt.PointingHandCursor)
        btn_cache.clicked.connect(self.cache_import_requested.emit)
        title_row.addWidget(btn_cache)

        btn_remove = QPushButton("🗑")
        btn_remove.setToolTip("移除当前文件")
        btn_remove.setFixedSize(28, 28)
        btn_remove.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.clicked.connect(self._on_remove_current)
        title_row.addWidget(btn_remove)

        file_header_layout.addLayout(title_row)

        # Export row: name input + buttons
        export_row = QHBoxLayout()
        export_row.setSpacing(4)
        export_row.addWidget(QLabel("导出名:"))
        self.export_name_input = QLineEdit()
        self.export_name_input.setPlaceholderText("默认使用文件名")
        self.export_name_input.setStyleSheet(INPUT_STYLE)
        self.export_name_input.textChanged.connect(
            lambda t: self.export_name_changed.emit(t)
        )
        export_row.addWidget(self.export_name_input, stretch=1)

        btn_export_cur = QPushButton("💾")
        btn_export_cur.setToolTip("导出当前结果")
        btn_export_cur.setFixedSize(28, 28)
        btn_export_cur.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_export_cur.setCursor(Qt.PointingHandCursor)
        btn_export_cur.clicked.connect(self.export_current.emit)
        export_row.addWidget(btn_export_cur)

        btn_export_batch = QPushButton("📦")
        btn_export_batch.setToolTip("批量导出")
        btn_export_batch.setFixedSize(28, 28)
        btn_export_batch.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_export_batch.setCursor(Qt.PointingHandCursor)
        btn_export_batch.clicked.connect(self.export_batch.emit)
        export_row.addWidget(btn_export_batch)

        file_header_layout.addLayout(export_row)
        outer.addWidget(file_header)

        # ━━ QSplitter: file list / segment section ━━
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_HOVER}; }}")

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_STYLE)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_click)
        splitter.addWidget(self.file_list)

        # Segment section (header + palette + list, all inside a container widget)
        segment_container = QWidget()
        segment_layout = QVBoxLayout(segment_container)
        segment_layout.setContentsMargins(16, 8, 16, 8)
        segment_layout.setSpacing(4)

        # Segment header
        seg_header = QHBoxLayout()
        self.seg_count_label = QLabel("📋 分段 (0/0)")
        self.seg_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        seg_header.addWidget(self.seg_count_label, stretch=1)

        btn_select_all = QPushButton("全选")
        btn_select_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.clicked.connect(self.select_all_clicked.emit)
        seg_header.addWidget(btn_select_all)

        btn_clear_all = QPushButton("全不选")
        btn_clear_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_clear_all.clicked.connect(self.clear_all_clicked.emit)
        seg_header.addWidget(btn_clear_all)

        btn_add_cmp = QPushButton("📌 对比")
        btn_add_cmp.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_add_cmp.setCursor(Qt.PointingHandCursor)
        btn_add_cmp.clicked.connect(self.add_to_comparison.emit)
        seg_header.addWidget(btn_add_cmp)

        segment_layout.addLayout(seg_header)

        # Palette row
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("🎨 配色:"))
        self.palette_combo = QComboBox()
        self.palette_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px 8px; font-size: 12px; }}"
        )
        self.palette_combo.currentTextChanged.connect(self.palette_scheme_changed.emit)
        palette_row.addWidget(self.palette_combo, stretch=1)

        btn_apply = QPushButton("应用")
        btn_apply.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.palette_apply_clicked.emit)
        palette_row.addWidget(btn_apply)

        btn_manage = QPushButton("⚙")
        btn_manage.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self.palette_manage_clicked.emit)
        palette_row.addWidget(btn_manage)

        segment_layout.addLayout(palette_row)

        # Segment list
        self.segment_list = QListWidget()
        self.segment_list.setStyleSheet(LIST_STYLE)
        segment_layout.addWidget(self.segment_list, stretch=1)

        splitter.addWidget(segment_container)

        # Default 40/60 split
        splitter.setSizes([150, 300])
        outer.addWidget(splitter, stretch=1)

        # Internal state
        self._file_paths: list[Path] = []
        self._processed: set[str] = set()
        self._segments: list[dict] = []
        self._active_index: int = 0
        self._checked_indices: set[int] = set()
        self._segment_colors: dict[int, str] = {}

    # ━━ File operations ━━

    def _on_select_files(self):
        paths_str, _ = QFileDialog.getOpenFileNames(
            self, "选择数据文件", "",
            "支持的文件 (*.tdms *.txt *.csv *.xlsx *.xls *.cor);;All files (*.*)"
        )
        if not paths_str:
            return
        paths = [Path(p) for p in paths_str]
        new_paths = [p for p in paths if p not in self._file_paths]
        self._file_paths.extend(new_paths)
        self._rebuild_file_list()
        if new_paths:
            self.files_selected.emit(new_paths)

    def _on_file_double_click(self, item: QListWidgetItem):
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            self.file_activated.emit(widget.file_path)

    def _on_remove_current(self):
        if not self._file_paths:
            return
        current = self._file_paths[0]
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{current.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._file_paths.remove(current)
            self._processed.discard(str(current))
            self._rebuild_file_list()
            self.file_removed.emit(current)

    def _rebuild_file_list(self):
        self.file_list.clear()
        for path in self._file_paths:
            item = QListWidgetItem()
            widget = FileListItem(path, str(path) in self._processed)
            widget.remove_clicked.connect(self._on_file_remove)
            item.setSizeHint(widget.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, widget)
        processed_count = len(self._processed)
        total = len(self._file_paths)
        self.file_count_label.setText(f"📂 文件 ({processed_count}/{total})")

    def _on_file_remove(self, path: Path):
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{path.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._file_paths.remove(path)
            self._processed.discard(str(path))
            self._rebuild_file_list()
            self.file_removed.emit(path)

    def set_file_paths(self, paths: list[Path], processed: set[str]) -> None:
        self._file_paths = list(paths)
        self._processed = set(processed)
        self._rebuild_file_list()

    def set_processed(self, path: Path) -> None:
        self._processed.add(str(path))
        self._rebuild_file_list()

    # ━━ Segment operations ━━

    def set_segments(self, segments: list[dict], active_index: int,
                     checked_indices: set[int], colors: dict[int, str],
                     fit_by_segment: dict) -> None:
        self._segments = segments
        self._active_index = active_index
        self._checked_indices = set(checked_indices)
        self._segment_colors = dict(colors)
        self._rebuild_segment_list(fit_by_segment)

    def _rebuild_segment_list(self, fit_by_segment: dict) -> None:
        self.segment_list.clear()
        for seg in self._segments:
            idx = seg["index"]
            color = self._segment_colors.get(idx, "#94a3b8")
            is_active = idx == self._active_index
            is_checked = idx in self._checked_indices
            fit = fit_by_segment.get(idx)
            r2 = fit.r2 if fit is not None else None

            item = QListWidgetItem()
            widget = SegmentItemWidget(idx, seg["label"], color, is_active, is_checked, r2)
            widget.activated.connect(self.segment_activated.emit)
            widget.toggled.connect(self.segment_toggled.emit)
            widget.color_clicked.connect(self.segment_color_changed.emit)
            item.setSizeHint(widget.sizeHint())
            self.segment_list.addItem(item)
            self.segment_list.setItemWidget(item, widget)

        self.seg_count_label.setText(
            f"📋 分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )

    def update_segment_state(self, active_index: int, checked_indices: set[int],
                              colors: dict[int, str], fit_by_segment: dict) -> None:
        """Lightweight update without full rebuild — updates each row widget."""
        self._active_index = active_index
        self._checked_indices = set(checked_indices)
        self._segment_colors = dict(colors)
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            w = self.segment_list.itemWidget(item)
            if isinstance(w, SegmentItemWidget):
                idx = w.segment_index
                fit = fit_by_segment.get(idx)
                w.update_state(
                    is_active=(idx == active_index),
                    is_checked=(idx in self._checked_indices),
                    r2=fit.r2 if fit is not None else None,
                    color=self._segment_colors.get(idx, "#94a3b8"),
                )
        self.seg_count_label.setText(
            f"📋 分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )

    # ━━ Palette schemes ━━

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)

    def set_export_name(self, name: str) -> None:
        self.export_name_input.setText(name)

    def get_export_name(self) -> str:
        return self.export_name_input.text().strip()
