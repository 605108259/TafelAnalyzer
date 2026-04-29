from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QColorDialog, QCheckBox,
)
from PySide6.QtCore import Signal, Qt, QEvent

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, BG_SELECTED, BG_HOVER, ACCENT_BUTTON_STYLE, DANGER,
)


class ComparisonItemWidget(QWidget):
    """Single row in comparison list."""

    visibility_toggled = Signal(str, bool)   # item_id, visible
    color_clicked = Signal(str)              # item_id
    rename_finished = Signal(str, str)       # item_id, new_name

    def __init__(self, item_id: str, display_name: str,
                 segment_label: str, color: str, visible: bool):
        super().__init__()
        self.item_id = item_id
        self._original_name = display_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Checkbox for visibility
        self.cb = QCheckBox()
        self.cb.setChecked(visible)
        self.cb.stateChanged.connect(
            lambda state: self.visibility_toggled.emit(item_id, bool(state))
        )
        layout.addWidget(self.cb)

        # Editable filename
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

        # Segment label
        seg_label = QLabel(segment_label)
        seg_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(seg_label)

        # Color dot
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; "
            f"border-radius: 10px; }}"
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
    """Side panel for cross-file comparison item management."""

    item_visibility_changed = Signal(str, bool)
    item_color_changed = Signal(str, str)    # item_id, hex_color
    item_renamed = Signal(str, str)          # item_id, new_name
    add_all_clicked = Signal()
    clear_all_clicked = Signal()
    delete_selected_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("\U0001f4ca 对比")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Action bar
        action_row = QHBoxLayout()
        self.btn_delete = QPushButton("\U0001f5d1 删除选中")
        self.btn_delete.setStyleSheet(BUTTON_STYLE)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self.delete_selected_clicked.emit)
        action_row.addWidget(self.btn_delete)

        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedWidth(32)
        self.btn_up.setStyleSheet(BUTTON_STYLE)
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.clicked.connect(self.move_up_clicked.emit)
        action_row.addWidget(self.btn_up)

        self.btn_down = QPushButton("↓")
        self.btn_down.setFixedWidth(32)
        self.btn_down.setStyleSheet(BUTTON_STYLE)
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.clicked.connect(self.move_down_clicked.emit)
        action_row.addWidget(self.btn_down)
        layout.addLayout(action_row)

        # Item list
        self.item_list = QListWidget()
        self.item_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        layout.addWidget(self.item_list, stretch=1)

        # Bottom buttons
        self.btn_add_all = QPushButton("\U0001f4e5 添加所有已处理段")
        self.btn_add_all.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_add_all.setCursor(Qt.PointingHandCursor)
        self.btn_add_all.clicked.connect(self.add_all_clicked.emit)
        layout.addWidget(self.btn_add_all)

        self.btn_clear = QPushButton("\U0001f5d1 清空全部")
        self.btn_clear.setStyleSheet(
            BUTTON_STYLE + f"QPushButton {{ color: {DANGER}; }}"
        )
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_all_clicked.emit)
        layout.addWidget(self.btn_clear)

    def set_items(self, items: list[dict]) -> None:
        """items: list of {item_id, display_name, segment_label, color, visible}"""
        self.item_list.clear()
        self._current_item_ids = [it["item_id"] for it in items]
        for data in items:
            widget = ComparisonItemWidget(
                data["item_id"], data["display_name"],
                data["segment_label"], data["color"], data["visible"],
            )
            widget.visibility_toggled.connect(self._on_visibility)
            widget.color_clicked.connect(self._on_color)
            widget.rename_finished.connect(self._on_rename)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.item_list.addItem(item)
            self.item_list.setItemWidget(item, widget)

    def _on_visibility(self, item_id: str, visible: bool):
        self.item_visibility_changed.emit(item_id, visible)

    def _on_color(self, item_id: str):
        color = QColorDialog.getColor()
        if color.isValid():
            self.item_color_changed.emit(item_id, color.name())

    def _on_rename(self, item_id: str, new_name: str):
        self.item_renamed.emit(item_id, new_name)
