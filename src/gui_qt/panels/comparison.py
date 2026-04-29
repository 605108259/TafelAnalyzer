from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QTextBrowser, QColorDialog, QCheckBox, QComboBox,
)
from PySide6.QtCore import Signal, Qt, QEvent

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, TEXT_PRIMARY, TEXT_SECONDARY, LIST_STYLE,
    ACCENT, ACCENT_BUTTON_STYLE, DANGER, SMALL_BUTTON_STYLE, INPUT_STYLE,
    BG_HOVER, BG_CARD,
)


class ComparisonItemWidget(QWidget):
    """Single row: ☑ visibility | name (dbl-click edit) | segment label | color swatch."""

    visibility_toggled = Signal(str, bool)   # item_id, visible
    color_clicked = Signal(str)              # item_id
    rename_finished = Signal(str, str)       # item_id, new_name

    def __init__(self, item_id: str, display_name: str,
                 segment_label: str, color: str, visible: bool):
        super().__init__()
        self.item_id = item_id
        self._original_name = display_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Checkbox
        self.cb = QCheckBox()
        self.cb.setChecked(visible)
        self.cb.stateChanged.connect(
            lambda state: self.visibility_toggled.emit(item_id, bool(state))
        )
        layout.addWidget(self.cb)

        # Editable name
        self.name_edit = QLineEdit(display_name)
        self.name_edit.setStyleSheet(
            f"QLineEdit {{ border: none; background: transparent; "
            f"color: {TEXT_PRIMARY}; font-size: 12px; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT}; border-radius: 4px; "
            f"background: white; padding: 2px 4px; }}"
        )
        self.name_edit.setReadOnly(True)
        self.name_edit.installEventFilter(self)
        self.name_edit.editingFinished.connect(self._on_rename)
        layout.addWidget(self.name_edit, stretch=1)

        # Segment
        seg = QLabel(segment_label)
        seg.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(seg)

        # Color
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(item_id))
        layout.addWidget(self.color_btn)

    def _on_rename(self):
        new_name = self.name_edit.text().strip()
        if new_name and new_name != self._original_name:
            self.rename_finished.emit(self.item_id, new_name)
        self._original_name = new_name or self._original_name
        if not new_name:
            self.name_edit.setText(self._original_name)

    def eventFilter(self, obj, event):
        if obj is self.name_edit and event.type() == QEvent.Type.MouseButtonDblClick:
            self.name_edit.setReadOnly(False)
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return True
        if obj is self.name_edit and event.type() == QEvent.Type.FocusOut:
            self.name_edit.setReadOnly(True)
        return super().eventFilter(obj, event)


class ComparisonPanel(QWidget):
    """Comparison side panel with header buttons, item list, result text."""

    # Item signals
    item_visibility_changed = Signal(str, bool)
    item_color_changed = Signal(str, str)
    item_renamed = Signal(str, str)

    # Action signals
    add_all_clicked = Signal()
    clear_all_clicked = Signal()
    delete_selected_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()
    export_clicked = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal()
    palette_manage_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Header with all action buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("📊 对比"))
        header.addStretch()

        for text, signal in [
            ("📥 添加", self.add_all_clicked),
            ("🗑 删除", self.delete_selected_clicked),
            ("↑", self.move_up_clicked),
            ("↓", self.move_down_clicked),
            ("🗑 清空", self.clear_all_clicked),
            ("💾 导出", self.export_clicked),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(SMALL_BUTTON_STYLE)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            header.addWidget(btn)

        layout.addLayout(header)

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

        layout.addLayout(palette_row)

        # Item list
        self.item_list = QListWidget()
        self.item_list.setStyleSheet(LIST_STYLE)
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
        """items: list of {item_id, display_name, segment_label, color, visible}"""
        self.item_list.clear()
        for data in items:
            widget = ComparisonItemWidget(
                data["item_id"], data["display_name"],
                data["segment_label"], data["color"], data["visible"],
            )
            widget.visibility_toggled.connect(self.item_visibility_changed.emit)
            widget.color_clicked.connect(self._on_color)
            widget.rename_finished.connect(self.item_renamed.emit)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.item_list.addItem(item)
            self.item_list.setItemWidget(item, widget)

    def _on_color(self, item_id: str):
        color = QColorDialog.getColor()
        if color.isValid():
            self.item_color_changed.emit(item_id, color.name())

    def set_result_text(self, text: str) -> None:
        self.result_text.setPlainText(text)

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)
