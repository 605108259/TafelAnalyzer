from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QComboBox, QSplitter,
    QFileDialog, QMessageBox, QToolButton, QInputDialog, QMenu,
)
from PySide6.QtCore import Signal, Qt, QEvent, QSize

from ui.theme import (
    PANEL_STYLE, SMALL_BUTTON_STYLE, DANGER_BUTTON_STYLE,
    ACCENT_BUTTON_STYLE, LIST_STYLE, SEGMENT_ITEM_STYLE,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, ACCENT, BG_HOVER, BG_SELECTED,
    ICON_BUTTON_STYLE, CheckmarkBox, COMBO_BOX_STYLE,
)
from ui.icons import line_icon
from ui.color_utils import swatch_button_style
from core.types import COMPARISON_COLORS as _DEFAULT_COLORS


COMPACT_FILE_ROW_THRESHOLD = 100


class FileListItem(QWidget):
    """Custom widget for each file row: name | ✓ badge | × remove."""

    remove_clicked = Signal(object)  # Path
    renamed = Signal(object, str)  # Path, new_name(stem)

    def __init__(self, file_path: Path, display_name: str, is_processed: bool = False):
        super().__init__()
        self.setObjectName("FileItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.file_path = file_path
        self._display_name = display_name
        self.setToolTip(str(file_path))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.name_edit = QLineEdit(display_name)
        self.name_edit.setReadOnly(True)
        self.name_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.name_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.name_edit.setFrame(False)
        self.name_edit.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; background: transparent;")
        self.name_edit.setToolTip(str(file_path))
        self.name_edit.editingFinished.connect(self._finish_rename)
        layout.addWidget(self.name_edit, stretch=1)

        self.badge = QLabel("✓")
        self.badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 12px;")
        self.badge.setVisible(is_processed)
        self.badge.installEventFilter(self)
        layout.addWidget(self.badge)

        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedSize(22, 22)
        self.remove_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 11px; color: #dc2626; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #fee2e2; }}"
        )
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.remove_btn.installEventFilter(self)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.file_path))
        layout.addWidget(self.remove_btn)

    def sizeHint(self):
        base = super().sizeHint()
        base.setHeight(max(base.height(), 28))
        return base

    def eventFilter(self, obj, event):
        if obj in (
            getattr(self, "badge", None),
            getattr(self, "remove_btn", None),
        ) and event.type() == QEvent.Type.ToolTip:
            return True
        return super().eventFilter(obj, event)

    def begin_rename(self) -> None:
        self.name_edit.setReadOnly(False)
        self.name_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.name_edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self.name_edit.selectAll()

    def set_display_name(self, display_name: str) -> None:
        self._display_name = display_name
        if self.name_edit.isReadOnly():
            self.name_edit.setText(display_name)

    def set_processed(self, is_processed: bool) -> None:
        self.badge.setVisible(bool(is_processed))

    def _finish_rename(self) -> None:
        if self.name_edit.isReadOnly():
            return
        text = self.name_edit.text().strip()
        if not text:
            text = self._display_name
            self.name_edit.setText(text)
        self.name_edit.setReadOnly(True)
        self.name_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._display_name = text
        self.renamed.emit(self.file_path, text)


class SegmentItemWidget(QWidget):
    """One row in segment list: ☑ checkbox | label | 🎨 color."""

    activated = Signal(int)
    toggled = Signal(int, bool)
    color_clicked = Signal(int)

    def __init__(self, index: int, label: str, color: str,
                 is_active: bool, is_checked: bool):
        super().__init__()
        self.setObjectName("SegmentItem")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(28)
        self.segment_index = index
        self._active = is_active
        self._hover = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Checkbox
        self.cb = CheckmarkBox(is_checked)
        self.cb.stateChanged.connect(lambda checked: self.toggled.emit(index, checked))
        layout.addWidget(self.cb)

        # Label
        name = QLabel(label)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; "
            "background: transparent; padding-left: 2px;"
        )
        layout.addWidget(name, stretch=1)

        # Color swatch
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(16, 16)
        self.color_btn.setStyleSheet(swatch_button_style(color, radius=4, border_width=1))
        self.color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(index))
        layout.addWidget(self.color_btn)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(SEGMENT_ITEM_STYLE)
        self._apply_bg()

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(28)
        return hint

    def event(self, event):
        if event.type() == QEvent.Type.HoverEnter:
            self._hover = True
            self._apply_bg()
        elif event.type() == QEvent.Type.HoverLeave:
            self._hover = False
            self._apply_bg()
        return super().event(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.segment_index)
        super().mousePressEvent(event)

    def update_state(self, is_active: bool, is_checked: bool, color: str):
        self._active = is_active
        self.cb.blockSignals(True)
        self.cb.setChecked(is_checked)
        self.cb.blockSignals(False)
        self.color_btn.setStyleSheet(
            swatch_button_style(color, radius=4, border_width=1)
        )
        self._apply_bg()

    def _apply_bg(self) -> None:
        if self._active:
            bg = BG_SELECTED
        elif self._hover:
            bg = BG_HOVER
        else:
            bg = "transparent"
        self.setStyleSheet(f"QWidget#SegmentItem {{ background: {bg}; border-radius: 6px; }}")


class FileSegmentPanel(QWidget):
    """Merged file selection + segment management panel with QSplitter."""

    # File signals
    files_selected = Signal(list)           # list[Path]
    file_activated = Signal(object)         # Path
    file_removed = Signal(object)           # Path
    file_renamed = Signal(object, str)      # Path, new_name(stem)
    cache_import_requested = Signal()

    # Segment signals
    segment_activated = Signal(int)
    segment_toggled = Signal(int, bool)
    segment_color_changed = Signal(int)
    select_all_clicked = Signal()
    clear_all_clicked = Signal()
    add_to_comparison = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal(str)
    palette_manage_clicked = Signal()

    # Export signals
    export_current = Signal()
    export_batch = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
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
        self.file_count_label = QLabel("文件 (0/0)")
        self.file_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        title_row.addWidget(self.file_count_label, stretch=1)

        for name, tip, cb in [
            ("folder", "选择数据文件", self._on_select_files),
            ("save", "导出当前结果", self.export_current.emit),
            ("package", "批量导出", self.export_batch.emit),
        ]:
            b = QToolButton()
            b.setIcon(line_icon(name, color=TEXT_PRIMARY, size=16))
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(ICON_BUTTON_STYLE)
            b.clicked.connect(cb)
            title_row.addWidget(b)

        file_header_layout.addLayout(title_row)
        outer.addWidget(file_header)

        # ━━ QSplitter: file list / segment section ━━
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_HOVER}; }}")

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_STYLE)
        self.file_list.setUniformItemSizes(True)
        self.file_list.installEventFilter(self)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_context_menu)
        self.file_list.itemClicked.connect(self._on_file_single_click)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_click)
        splitter.addWidget(self.file_list)

        # Segment section (header + palette + list, all inside a container widget)
        segment_container = QWidget()
        segment_layout = QVBoxLayout(segment_container)
        segment_layout.setContentsMargins(16, 8, 16, 8)
        segment_layout.setSpacing(4)

        # Segment header
        seg_header = QHBoxLayout()
        self.seg_count_label = QLabel("分段 (0/0)")
        self.seg_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        seg_header.addWidget(self.seg_count_label, stretch=1)

        btn_select_all = QPushButton("全选")
        btn_select_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all.clicked.connect(self.select_all_clicked.emit)
        seg_header.addWidget(btn_select_all)

        btn_clear_all = QPushButton("全不选")
        btn_clear_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_clear_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_all.clicked.connect(self.clear_all_clicked.emit)
        seg_header.addWidget(btn_clear_all)

        btn_add_cmp = QPushButton("对比")
        btn_add_cmp.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_add_cmp.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_cmp.clicked.connect(self.add_to_comparison.emit)
        seg_header.addWidget(btn_add_cmp)

        segment_layout.addLayout(seg_header)

        # Palette row
        palette_row = QHBoxLayout()
        palette_lbl = QLabel("配色:")
        palette_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        palette_row.addWidget(palette_lbl)
        self.palette_combo = QComboBox()
        self.palette_combo.setStyleSheet(COMBO_BOX_STYLE)
        self.palette_combo.currentTextChanged.connect(self.palette_scheme_changed.emit)
        palette_row.addWidget(self.palette_combo, stretch=1)

        self.palette_apply_mode = QComboBox()
        self.palette_apply_mode.setStyleSheet(COMBO_BOX_STYLE)
        self.palette_apply_mode.addItem("逐个", "sequential")
        self.palette_apply_mode.addItem("插值", "interpolate")
        self.palette_apply_mode.setFixedWidth(64)
        palette_row.addWidget(self.palette_apply_mode)

        btn_apply = QPushButton("应用")
        btn_apply.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.clicked.connect(
            lambda: self.palette_apply_clicked.emit(self.palette_apply_mode.currentData() or "sequential")
        )
        palette_row.addWidget(btn_apply)

        btn_manage = QToolButton()
        btn_manage.setIcon(line_icon("gear", color=TEXT_SECONDARY, size=14))
        btn_manage.setToolTip("管理配色方案")
        btn_manage.setStyleSheet(ICON_BUTTON_STYLE)
        btn_manage.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manage.clicked.connect(self.palette_manage_clicked.emit)
        palette_row.addWidget(btn_manage)

        segment_layout.addLayout(palette_row)

        # Segment list
        self.segment_list = QListWidget()
        self.segment_list.setStyleSheet(LIST_STYLE)
        self.segment_list.setUniformItemSizes(True)
        self.segment_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        segment_layout.addWidget(self.segment_list, stretch=1)

        splitter.addWidget(segment_container)

        # Default 40/60 split
        splitter.setSizes([150, 300])
        outer.addWidget(splitter, stretch=1)

        # Internal state
        self._file_paths: list[Path] = []
        self._processed: set[str] = set()
        self._file_names: dict[str, str] = {}
        self._active_file_path: Path | None = None
        self._compact_file_rows = False
        self._segments: list[dict] = []
        self._active_index: int = 0
        self._checked_indices: set[int] = set()
        self._segment_colors: dict[int, str] = {}

    # ━━ File operations ━━

    def set_heavy_list_updates_enabled(self, enabled: bool) -> None:
        """Freeze expensive list repaints while the file panel is hidden."""
        for view in (self.file_list, self.segment_list):
            view.setUpdatesEnabled(enabled)
            viewport = view.viewport()
            if viewport is not None:
                viewport.setUpdatesEnabled(enabled)
                if enabled:
                    viewport.update()
            if enabled:
                view.update()

    def eventFilter(self, obj, event):
        if obj is self.file_list and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Delete:
                self._on_remove_current()
                return True
            if key == Qt.Key.Key_F2:
                current = self._path_from_file_item(self.file_list.currentItem())
                if current is not None:
                    self._rename_file_path(current)
                return True
        return super().eventFilter(obj, event)

    def _should_use_compact_file_rows(self) -> bool:
        return len(self._file_paths) > COMPACT_FILE_ROW_THRESHOLD

    def _path_from_file_item(self, item: QListWidgetItem | None) -> Path | None:
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(data)) if data else None

    def _update_compact_file_item(self, item: QListWidgetItem, path: Path) -> None:
        display_name = self._file_names.get(str(path), path.stem)
        processed = str(path) in self._processed
        prefix = "✓ " if processed else "  "
        item.setText(f"{prefix}{display_name}")
        item.setToolTip(str(path))
        item.setData(Qt.ItemDataRole.UserRole, str(path))

    def _rename_file_path(self, path: Path) -> None:
        current_name = self._file_names.get(str(path), path.stem)
        new_name, ok = QInputDialog.getText(
            self,
            "重命名文件",
            "显示名称:",
            text=current_name,
        )
        if ok and new_name.strip():
            self._on_file_renamed(path, new_name.strip())

    def _on_file_context_menu(self, pos) -> None:
        item = self.file_list.itemAt(pos)
        path = self._path_from_file_item(item)
        if path is None and item is not None:
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, FileListItem):
                path = widget.file_path
        if path is None:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        remove_action = menu.addAction("移除")
        chosen = menu.exec(self.file_list.mapToGlobal(pos))
        if chosen == rename_action:
            if item is not None and not self._compact_file_rows:
                widget = self.file_list.itemWidget(item)
                if isinstance(widget, FileListItem):
                    widget.begin_rename()
                    return
            self._rename_file_path(path)
        elif chosen == remove_action:
            self._on_file_remove(path)

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
        for p in new_paths:
            self._file_names.setdefault(str(p), p.stem)
        self._rebuild_file_list()
        if new_paths:
            self.files_selected.emit(new_paths)

    def _on_file_double_click(self, item: QListWidgetItem):
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            widget.begin_rename()
            return
        path = self._path_from_file_item(item)
        if path is not None:
            self._rename_file_path(path)

    def _on_file_single_click(self, item: QListWidgetItem):
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            self._active_file_path = widget.file_path
            self._update_file_highlight()
            self.file_activated.emit(widget.file_path)
            return
        path = self._path_from_file_item(item)
        if path is not None:
            self._active_file_path = path
            self._update_file_highlight()
            self.file_activated.emit(path)

    def _on_remove_current(self):
        if not self._file_paths:
            return
        current_row = self.file_list.currentRow()
        if current_row < 0 or current_row >= len(self._file_paths):
            current = self._file_paths[0]  # fallback
        else:
            current = self._file_paths[current_row]
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{current.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.file_removed.emit(current)

    def _rebuild_file_list(self):
        scroll_value = self.file_list.verticalScrollBar().value()
        self._compact_file_rows = self._should_use_compact_file_rows()
        self._clear_file_widgets()
        self.file_list.clear()
        for path in self._file_paths:
            self._append_file_row(path)
        self._update_file_count()
        self._update_file_highlight()
        self.file_list.verticalScrollBar().setValue(scroll_value)

    def _clear_file_widgets(self) -> None:
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            widget = self.file_list.itemWidget(item)
            if widget is None:
                continue
            self.file_list.removeItemWidget(item)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()

    def _append_file_row(self, path: Path) -> None:
        if self._compact_file_rows:
            self._append_compact_file_row(path)
            return
        item = QListWidgetItem()
        display_name = self._file_names.get(str(path), path.stem)
        widget = FileListItem(path, display_name, str(path) in self._processed)
        widget.remove_clicked.connect(self._on_file_remove)
        widget.renamed.connect(self._on_file_renamed)
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)

    def _append_compact_file_row(self, path: Path) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        item.setSizeHint(QSize(0, 28))
        self.file_list.addItem(item)
        self._update_compact_file_item(item, path)

    def remove_file_path(self, path: Path) -> None:
        """Remove a single file path from the list without full rebuild."""
        row = self._row_for_path(path)
        if row < 0:
            return
        self._file_paths.pop(row)
        self._remove_file_row(row)
        self._update_file_count()

    def _remove_file_row(self, row: int) -> None:
        if row < 0 or row >= self.file_list.count():
            return
        item = self.file_list.item(row)
        widget = self.file_list.itemWidget(item)
        if widget is not None:
            self.file_list.removeItemWidget(item)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self.file_list.takeItem(row)

    def _row_for_path(self, path: Path) -> int:
        for row, candidate in enumerate(self._file_paths):
            if candidate == path:
                return row
        return -1

    def _update_file_count(self) -> None:
        processed_count = sum(1 for path in self._file_paths if str(path) in self._processed)
        total = len(self._file_paths)
        self.file_count_label.setText(f"文件 ({processed_count}/{total})")

    def _update_file_row(self, row: int, path: Path) -> None:
        if row < 0 or row >= self.file_list.count():
            return
        item = self.file_list.item(row)
        if self._compact_file_rows:
            self._update_compact_file_item(item, path)
            return
        widget = self.file_list.itemWidget(item)
        if not isinstance(widget, FileListItem) or widget.file_path != path:
            self._rebuild_file_list()
            return
        widget.set_display_name(self._file_names.get(str(path), path.stem))
        widget.set_processed(str(path) in self._processed)
        item.setSizeHint(widget.sizeHint())

    def _sync_file_rows_incremental(self, old_paths: list[Path], new_paths: list[Path]) -> bool:
        if self.file_list.count() != len(old_paths):
            return False
        survivors = [path for path in old_paths if path in new_paths]
        if new_paths[:len(survivors)] != survivors:
            return False
        scroll_value = self.file_list.verticalScrollBar().value()
        survivor_set = set(survivors)
        for row in range(len(old_paths) - 1, -1, -1):
            if old_paths[row] not in survivor_set:
                self._remove_file_row(row)
        for path in new_paths[len(survivors):]:
            self._append_file_row(path)
        for row, path in enumerate(new_paths):
            self._update_file_row(row, path)
        self.file_list.verticalScrollBar().setValue(scroll_value)
        return True

    def _on_file_remove(self, path: Path):
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.file_removed.emit(path)

    def _on_file_renamed(self, path: Path, new_name: str) -> None:
        self._file_names[str(path)] = new_name
        self.file_renamed.emit(path, new_name)

    def set_file_paths(self, paths: list[Path], processed: set[str], *, names: dict[str, str] | None = None) -> None:
        old_paths = list(self._file_paths)
        old_compact = self._compact_file_rows
        self._file_paths = list(paths)
        self._processed = set(processed)
        if names is not None:
            self._file_names = dict(names)
        for p in self._file_paths:
            self._file_names.setdefault(str(p), p.stem)
        if old_compact != self._should_use_compact_file_rows():
            self._rebuild_file_list()
            return
        if old_paths != self._file_paths:
            if not self._sync_file_rows_incremental(old_paths, self._file_paths):
                self._rebuild_file_list()
                return
        else:
            for row, path in enumerate(self._file_paths):
                self._update_file_row(row, path)
        self._update_file_count()
        self._update_file_highlight()

    def set_processed(self, path: Path) -> None:
        self._processed.add(str(path))
        self._update_file_row(self._row_for_path(path), path)
        self._update_file_count()
        self._update_file_highlight()

    def set_current_file(self, path: Path) -> None:
        try:
            row = self._file_paths.index(path)
        except ValueError:
            return
        self._active_file_path = path
        self.file_list.setCurrentRow(row)
        self._update_file_highlight()

    def _update_file_highlight(self) -> None:
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if self._compact_file_rows:
                item.setSelected(self._path_from_file_item(item) == self._active_file_path)
                continue
            widget = self.file_list.itemWidget(item)
            if not isinstance(widget, FileListItem):
                continue
            is_active = widget.file_path == self._active_file_path
            if is_active:
                widget.setStyleSheet(
                    f"QWidget#FileItem {{ background: {BG_SELECTED}; border-radius: 6px; }}"
                )
            else:
                widget.setStyleSheet(
                    f"QWidget#FileItem {{ background: transparent; }}"
                    f"QWidget#FileItem:hover {{ background: {BG_HOVER}; border-radius: 6px; }}"
                )

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
            default_color = _DEFAULT_COLORS[idx % len(_DEFAULT_COLORS)]
            color = self._segment_colors.get(idx) or default_color
            is_active = idx == self._active_index
            is_checked = idx in self._checked_indices

            item = QListWidgetItem()
            widget = SegmentItemWidget(idx, seg["label"], color, is_active, is_checked)
            widget.activated.connect(self.segment_activated.emit)
            widget.toggled.connect(self.segment_toggled.emit)
            widget.color_clicked.connect(self.segment_color_changed.emit)
            item.setSizeHint(widget.sizeHint())
            self.segment_list.addItem(item)
            self.segment_list.setItemWidget(item, widget)

        self.seg_count_label.setText(
            f"分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            w = self.segment_list.itemWidget(item)
            if isinstance(w, SegmentItemWidget) and w.segment_index == self._active_index:
                self.segment_list.setCurrentRow(i)
                break

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
                w.update_state(
                    is_active=(idx == active_index),
                    is_checked=(idx in self._checked_indices),
                    color=self._segment_colors.get(idx, _DEFAULT_COLORS[idx % len(_DEFAULT_COLORS)]),
                )
        self.seg_count_label.setText(
            f"分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )

    # ━━ Palette schemes ━━

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)
