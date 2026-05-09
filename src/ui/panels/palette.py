from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QScrollArea, QMessageBox, QLineEdit, QToolButton,
)
from PySide6.QtCore import Signal, Qt

from ui.theme import (
    PANEL_STYLE, BUTTON_STYLE, ACCENT_BUTTON_STYLE, SMALL_BUTTON_STYLE,
    DANGER_BUTTON_STYLE, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT,
    BG_CARD, BG_HOVER, COMBO_BOX_STYLE, SCROLL_AREA_STYLE, BORDER,
    INPUT_STYLE, ICON_BUTTON_STYLE, DANGER,
)
from ui.color_utils import is_hex_color, normalize_hex_color, swatch_button_style
from ui.layout_utils import clear_layout


class ColorSwatch(QPushButton):
    """Clickable color square with hex label."""

    color_clicked = Signal(int, str)  # index, current_hex

    def __init__(self, index: int, hex_color: str):
        super().__init__()
        self._index = index
        self._hex = hex_color
        self.setFixedSize(72, 28)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{index + 1}: {hex_color}")
        self._update_style()
        self.clicked.connect(lambda: self.color_clicked.emit(self._index, self._hex))

    def _update_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._hex}; border: 1px solid {BORDER}; border-radius: 6px; }}"
            f"QPushButton:hover {{ border-color: {BORDER}; }}"
            f"QPushButton:pressed {{ border-color: {BORDER}; }}"
            f"QPushButton:focus {{ border-color: {BORDER}; outline: none; }}"
        )

    def set_color(self, hex_color: str):
        self._hex = normalize_hex_color(hex_color)
        self._update_style()


class ColorRow(QWidget):
    color_changed = Signal(int, str)
    selected = Signal(int)

    def __init__(self, index: int, hex_color: str, _segment_name: str):
        super().__init__()
        self._index = index
        self._hex = normalize_hex_color(hex_color)
        self._selected = False
        self.setObjectName("PaletteColorRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.index_label = QLabel(str(index + 1))
        self.index_label.setAlignment(Qt.AlignCenter)
        self.index_label.setFixedWidth(28)
        self.index_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        self.index_label.installEventFilter(self)
        layout.addWidget(self.index_label)

        self.swatch = ColorSwatch(index, self._hex)
        self.swatch.installEventFilter(self)
        self.swatch.color_clicked.connect(self._pick_color)
        layout.addWidget(self.swatch)

        self.hex_edit = QLineEdit(self._hex)
        self.hex_edit.setStyleSheet(INPUT_STYLE)
        self.hex_edit.setPlaceholderText("#f0f4f7")
        self.hex_edit.installEventFilter(self)
        self.hex_edit.editingFinished.connect(self._commit_hex)
        layout.addWidget(self.hex_edit, stretch=1)
        self._update_selected_style()

    def set_color(self, hex_color: str) -> None:
        self._hex = normalize_hex_color(hex_color)
        self.swatch.set_color(self._hex)
        self.hex_edit.setText(self._hex)

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._update_selected_style()

    def _update_selected_style(self) -> None:
        bg = "#dbeafe" if self._selected else "transparent"
        border = ACCENT if self._selected else "transparent"
        label_color = TEXT_PRIMARY if self._selected else TEXT_SECONDARY
        edit_bg = "#eff6ff" if self._selected else BG_CARD
        self.setStyleSheet(
            f"QWidget#PaletteColorRow {{ background: {bg}; border: 1px solid {border}; border-radius: 6px; }}"
        )
        self.index_label.setStyleSheet(f"color: {label_color}; font-size: 11px; font-weight: 700;")
        self.hex_edit.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 8px; "
            f"background: {edit_bg}; color: {TEXT_PRIMARY}; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
        )

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self._index)
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        watched = {
            widget
            for widget in (
                getattr(self, "hex_edit", None),
                getattr(self, "swatch", None),
                getattr(self, "index_label", None),
            )
            if widget is not None
        }
        if obj in watched and event.type() in {
            event.Type.FocusIn,
            event.Type.MouseButtonPress,
        }:
            self.selected.emit(self._index)
        return super().eventFilter(obj, event)

    def _pick_color(self, index: int, current_hex: str) -> None:
        self.selected.emit(index)

    def _commit_hex(self) -> None:
        text = self.hex_edit.text().strip()
        if not is_hex_color(text):
            self.hex_edit.setText(self._hex)
            return
        self.set_color(normalize_hex_color(text))
        self.color_changed.emit(self._index, self._hex)


class PaletteSidebar(QWidget):
    """Left sidebar for palette scheme management — Origin-style compact."""

    scheme_changed = Signal(str)
    color_changed = Signal(int, str)       # index, new_hex
    color_count_changed = Signal(int)
    apply_to_current_clicked = Signal()
    save_as_new_clicked = Signal(str)     # name
    delete_scheme_clicked = Signal(str)   # name
    color_move_requested = Signal(int, int)  # index, delta
    color_add_requested = Signal(int)
    color_remove_requested = Signal(int)
    colors_reverse_requested = Signal()
    colors_gradient_requested = Signal()
    default_reset_requested = Signal()
    color_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title + scheme selector
        title_lbl = QLabel("配色方案")
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        layout.addWidget(title_lbl)
        self.scheme_combo = QComboBox()
        self.scheme_combo.setStyleSheet(COMBO_BOX_STYLE)
        self.scheme_combo.currentTextChanged.connect(self.scheme_changed.emit)
        layout.addWidget(self.scheme_combo)

        # Palette slot toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        def tool_btn(text: str, tip: str, callback, danger: bool = False) -> QToolButton:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                ICON_BUTTON_STYLE
                + (f"QToolButton {{ color: {DANGER}; }}" if danger else f"QToolButton {{ color: {TEXT_SECONDARY}; }}")
            )
            btn.clicked.connect(callback)
            return btn

        toolbar.addWidget(tool_btn("↑", "上移当前颜色", lambda: self.color_move_requested.emit(self._selected_index, -1)))
        toolbar.addWidget(tool_btn("↓", "下移当前颜色", lambda: self.color_move_requested.emit(self._selected_index, 1)))
        toolbar.addWidget(tool_btn("+", "在当前颜色后添加", lambda: self.color_add_requested.emit(self._selected_index)))
        toolbar.addWidget(tool_btn("-", "删除当前颜色", lambda: self.color_remove_requested.emit(self._selected_index), danger=True))
        toolbar.addWidget(tool_btn("↔", "反转颜色顺序", self.colors_reverse_requested.emit))
        toolbar.addWidget(tool_btn("渐", "按首尾颜色渐变填充", self.colors_gradient_requested.emit))
        layout.addLayout(toolbar)

        # Gradient preview
        self.gradient_preview = QWidget()
        self.gradient_preview.setObjectName("GradientPreview")
        self.gradient_preview.setFixedHeight(20)
        self.gradient_preview.setStyleSheet(
            f"QWidget#GradientPreview {{ border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        layout.addWidget(self.gradient_preview)

        # Color swatch grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLL_AREA_STYLE)
        scroll_widget = QWidget()
        self.swatch_layout = QVBoxLayout(scroll_widget)
        self.swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.swatch_layout.setSpacing(4)
        self.swatch_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        self.count_combo = QComboBox()
        self.count_combo.hide()

        # Action buttons
        btn_apply = QPushButton("保存方案")
        btn_apply.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.apply_to_current_clicked.emit)
        layout.addWidget(btn_apply)

        btn_save = QPushButton("另存为新方案")
        btn_save.setStyleSheet(BUTTON_STYLE)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._on_save_as_new)
        layout.addWidget(btn_save)

        btn_delete = QPushButton("删除方案")
        btn_delete.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._on_delete)
        layout.addWidget(btn_delete)

        # Internal state
        self._rows: list[ColorRow] = []
        self._scheme_names: list[str] = []
        self._selected_index = 0

    def set_schemes(self, schemes: list[str], active: str) -> None:
        self._scheme_names = schemes
        self.scheme_combo.blockSignals(True)
        self.scheme_combo.clear()
        self.scheme_combo.addItems(schemes)
        if active in schemes:
            self.scheme_combo.setCurrentText(active)
        self.scheme_combo.blockSignals(False)

    def set_colors(self, colors: list[str], segment_names: list[str]) -> None:
        """colors: list of hex strings, one per slot."""
        clear_layout(self.swatch_layout)
        self._rows.clear()

        # Add swatch rows
        for i, (hex_color, name) in enumerate(zip(colors, segment_names)):
            row = ColorRow(i, hex_color, name)
            row.color_changed.connect(self._on_color_changed)
            row.selected.connect(self._select_index)
            self._rows.append(row)
            self.swatch_layout.addWidget(row)

        self.swatch_layout.addStretch()
        self._selected_index = min(self._selected_index, max(len(self._rows) - 1, 0))
        self._sync_row_selection()
        self._update_gradient(colors)

    def _on_color_changed(self, index: int, new_hex: str):
        self._select_index(index)
        self.color_changed.emit(index, new_hex)
        all_colors = [row._hex for row in self._rows]
        self._update_gradient(all_colors)

    def _select_index(self, index: int, *, notify: bool = True) -> None:
        if not self._rows:
            self._selected_index = 0
            return
        self._selected_index = max(0, min(int(index), len(self._rows) - 1))
        self._sync_row_selection()
        if notify:
            self.color_selected.emit(self._selected_index)

    def _sync_row_selection(self) -> None:
        for row in self._rows:
            row.set_selected(row._index == self._selected_index)

    def _update_gradient(self, colors: list[str]):
        if not colors:
            return
        stops = ", ".join(
            f"stop:{i / max(len(colors) - 1, 1):.3f} {c}"
            for i, c in enumerate(colors)
        )
        self.gradient_preview.setStyleSheet(
            f"QWidget#GradientPreview {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops}); "
            f"border: 1px solid {BORDER}; border-radius: 6px; }}"
        )

    def _on_save_as_new(self):
        self.save_as_new_clicked.emit(self.scheme_combo.currentText())

    def _on_delete(self):
        name = self.scheme_combo.currentText()
        if not name:
            return
        confirm = QMessageBox.question(
            self, "确认删除", f"确定要删除方案 \"{name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.delete_scheme_clicked.emit(name)

    def get_active_scheme(self) -> str:
        return self.scheme_combo.currentText()

    def set_selected_index(self, index: int) -> None:
        self._select_index(index, notify=False)
