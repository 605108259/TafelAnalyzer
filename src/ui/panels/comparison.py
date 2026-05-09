from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QTextBrowser, QColorDialog, QComboBox,
    QToolButton,
)
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QColor

from ui.theme import (
    BUTTON_STYLE, PANEL_STYLE, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, ACCENT_BUTTON_STYLE, DANGER, SMALL_BUTTON_STYLE, INPUT_STYLE,
    BG_HOVER, BG_CARD, CheckmarkBox, ICON_BUTTON_STYLE, COMBO_BOX_STYLE,
)
from ui.color_utils import swatch_button_style
from ui.icons import line_icon


class RenameLineEdit(QLineEdit):
    commit_requested = Signal()
    cancel_requested = Signal()

    def focusOutEvent(self, event):
        if not self.isReadOnly():
            self.commit_requested.emit()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ComparisonItemWidget(QWidget):
    """Single row: ☑ visibility | name with segment (dbl-click edit) | color swatch | × remove."""

    visibility_toggled = Signal(str, bool)   # item_id, visible
    color_clicked = Signal(str)              # item_id
    rename_finished = Signal(str, str)       # item_id, new_name
    remove_clicked = Signal(str)             # item_id
    row_clicked = Signal()                   # emitted on any left-click

    def __init__(self, item_id: str, display_name: str,
                 color: str, visible: bool):
        super().__init__()
        self.setObjectName("ComparisonItem")
        self.item_id = item_id
        self._color = color
        self._original_name = display_name
        self._segment_label = ""
        self._highlighted = False
        self._editing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignVCenter)

        self.cb = CheckmarkBox(visible)
        self.cb.stateChanged.connect(
            lambda checked: self.visibility_toggled.emit(item_id, checked)
        )
        layout.addWidget(self.cb)

        self.name_edit = RenameLineEdit(display_name)
        self.name_edit.setStyleSheet(
            f"QLineEdit {{ border: 1px solid transparent; border-radius: 4px; "
            f"background: transparent; padding: 2px 4px; "
            f"color: {TEXT_PRIMARY}; font-size: 12px; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT}; "
            f"background: white; }}"
        )
        self.name_edit.setReadOnly(True)
        self.name_edit.commit_requested.connect(self._commit_rename)
        self.name_edit.cancel_requested.connect(self._cancel_rename)
        layout.addWidget(self.name_edit, stretch=1)

        self.segment_lbl = QLabel()
        self.segment_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self.segment_lbl.hide()
        layout.addWidget(self.segment_lbl)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(swatch_button_style(color, radius=10, border_width=2))
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(item_id))
        layout.addWidget(self.color_btn)

        self.rm_btn = QToolButton()
        self.rm_btn.setIcon(line_icon("x", color=TEXT_SECONDARY, size=14))
        self.rm_btn.setToolTip("移除")
        self.rm_btn.setCursor(Qt.PointingHandCursor)
        self.rm_btn.setStyleSheet(ICON_BUTTON_STYLE)
        self.rm_btn.clicked.connect(lambda: self.remove_clicked.emit(item_id))
        layout.addWidget(self.rm_btn)

        for w in (self.cb, self.name_edit, self.color_btn, self.rm_btn):
            w.installEventFilter(self)

    def sizeHint(self):
        base = super().sizeHint()
        base.setHeight(max(base.height(), 28))
        return base

    def begin_rename(self) -> None:
        self._editing = True
        self.name_edit.setReadOnly(False)
        self.name_edit.setFocus(Qt.MouseFocusReason)
        self.name_edit.selectAll()

    def _commit_rename(self):
        if not self._editing:
            return
        new_name = self.name_edit.text().strip()
        if not new_name:
            self.name_edit.setText(self._original_name)
            self._editing = False
            self.name_edit.setReadOnly(True)
            return
        self._editing = False
        self.name_edit.setReadOnly(True)
        if new_name != self._original_name:
            self.set_display_name(new_name, self._segment_label)
            self.rename_finished.emit(self.item_id, new_name)

    def _cancel_rename(self) -> None:
        self._editing = False
        self.name_edit.setText(self._original_name)
        self.name_edit.setReadOnly(True)

    def set_display_name(self, display_name: str, segment_label: str = "") -> None:
        self._original_name = display_name
        self._segment_label = segment_label
        self.name_edit.setText(display_name)
        self.segment_lbl.setText(segment_label)
        self.segment_lbl.setVisible(bool(segment_label))

    def set_highlighted(self, on: bool):
        self._highlighted = on
        if on:
            self.setStyleSheet(
                f"QWidget#ComparisonItem {{ background: rgba(37, 99, 235, 20); "
                f"border-left: 3px solid #2563eb; border-radius: 4px; }}"
            )
        else:
            self.setStyleSheet("")

    def eventFilter(self, obj, event):
        if obj is self.name_edit and event.type() == QEvent.Type.MouseButtonDblClick:
            self.begin_rename()
            return True
        if obj is self.name_edit and event.type() == QEvent.Type.FocusOut:
            self._commit_rename()
        # Forward single clicks on child widgets to trigger highlight
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            self.row_clicked.emit()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.row_clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.begin_rename()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ComparisonPanel(QWidget):
    """Comparison side panel with header buttons, item list, result text."""

    # Item signals
    item_visibility_changed = Signal(str, bool)
    item_color_changed = Signal(str, str)
    item_renamed = Signal(str, str)
    item_remove_clicked = Signal(str)
    item_clicked = Signal(int)

    # Action signals
    clear_all_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal(str)
    palette_manage_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(PANEL_STYLE)
        self._highlighted_row = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Header with action buttons
        header = QHBoxLayout()
        title_lbl = QLabel("对比")
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold;")
        header.addWidget(title_lbl)
        header.addStretch()

        for name, tip, sig in [
            ("arrow-up", "上移", self.move_up_clicked),
            ("arrow-down", "下移", self.move_down_clicked),
            ("trash", "清空", self.clear_all_clicked),
        ]:
            btn = QToolButton()
            btn.setIcon(line_icon(name, color=TEXT_PRIMARY, size=16))
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(ICON_BUTTON_STYLE)
            btn.clicked.connect(sig.emit)
            header.addWidget(btn)

        layout.addLayout(header)

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
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(
            lambda: self.palette_apply_clicked.emit(self.palette_apply_mode.currentData() or "sequential")
        )
        palette_row.addWidget(btn_apply)

        btn_manage = QToolButton()
        btn_manage.setIcon(line_icon("gear", color=TEXT_SECONDARY, size=14))
        btn_manage.setToolTip("管理配色方案")
        btn_manage.setStyleSheet(ICON_BUTTON_STYLE)
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self.palette_manage_clicked.emit)
        palette_row.addWidget(btn_manage)

        layout.addLayout(palette_row)

        # Item list
        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.NoSelection)
        self.item_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}"
            f"QListWidget::item {{ background: transparent; padding: 0px; }}"
        )
        self.item_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.item_list, stretch=1)

        # Result text
        self.result_text = QTextBrowser()
        self.result_text.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid #e2e8f0; border-radius: 4px; "
            f"background: {BG_HOVER}; color: {TEXT_PRIMARY}; font-size: 12px; padding: 4px; }}"
        )
        self.result_text.setFixedHeight(120)
        layout.addWidget(self.result_text)

    def set_items(self, items: list[dict]) -> None:
        """items: list of {item_id, edit_name, segment_label, color, visible}"""
        self._clear_items()
        self.item_list.clear()
        for data in items:
            widget = ComparisonItemWidget(
                data["item_id"], data.get("edit_name") or data["display_name"],
                data["color"], data["visible"],
            )
            widget.set_display_name(
                data.get("edit_name") or data["display_name"],
                data.get("segment_label", ""),
            )
            widget.visibility_toggled.connect(self.item_visibility_changed.emit)
            widget.color_clicked.connect(self._on_color)
            widget.rename_finished.connect(
                lambda item_id, name: self.item_renamed.emit(item_id, name)
            )
            widget.remove_clicked.connect(self.item_remove_clicked.emit)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.item_list.addItem(item)
            self.item_list.setItemWidget(item, widget)
            widget.row_clicked.connect(lambda _item=item: self._on_item_clicked(_item))

        # Reapply highlight after rebuild
        if 0 <= self._highlighted_row < self.item_list.count():
            w = self.item_list.itemWidget(self.item_list.item(self._highlighted_row))
            if w:
                w.set_highlighted(True)

    def _clear_items(self) -> None:
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            widget = self.item_list.itemWidget(item)
            if widget is None:
                continue
            self.item_list.removeItemWidget(item)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()

    def update_item_name(self, item_id: str, display_name: str, segment_label: str = "") -> None:
        for row in range(self.item_list.count()):
            widget = self.item_list.itemWidget(self.item_list.item(row))
            if isinstance(widget, ComparisonItemWidget) and widget.item_id == item_id:
                widget.set_display_name(display_name, segment_label)
                return

    def set_highlighted(self, row: int) -> None:
        """Set which row is highlighted (visually, no selection box)."""
        if 0 <= self._highlighted_row < self.item_list.count():
            prev = self.item_list.itemWidget(self.item_list.item(self._highlighted_row))
            if prev:
                prev.set_highlighted(False)
        self._highlighted_row = row
        if 0 <= row < self.item_list.count():
            w = self.item_list.itemWidget(self.item_list.item(row))
            if w:
                w.set_highlighted(True)

    def highlighted_row(self) -> int:
        return self._highlighted_row

    def _on_color(self, item_id: str):
        current = "#2563eb"
        for row in range(self.item_list.count()):
            widget = self.item_list.itemWidget(self.item_list.item(row))
            if isinstance(widget, ComparisonItemWidget) and widget.item_id == item_id:
                current = widget._color
                break
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            self.item_color_changed.emit(item_id, color.name())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        row = self.item_list.row(item)
        self.item_clicked.emit(row)

    def set_result_text(self, text: str) -> None:
        self.result_text.setPlainText(text)

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)
