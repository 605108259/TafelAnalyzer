from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QScrollArea, QColorDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    PANEL_STYLE, BUTTON_STYLE, ACCENT_BUTTON_STYLE, SMALL_BUTTON_STYLE,
    DANGER_BUTTON_STYLE, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT,
    BG_CARD, BG_HOVER,
)


class ColorSwatch(QPushButton):
    """Clickable color square with hex label."""

    color_clicked = Signal(int, str)  # index, current_hex

    def __init__(self, index: int, hex_color: str, segment_name: str):
        super().__init__()
        self._index = index
        self._hex = hex_color
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{segment_name}: {hex_color}")
        self._update_style()
        self.clicked.connect(lambda: self.color_clicked.emit(self._index, self._hex))

    def _update_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._hex}; border: 2px solid white; border-radius: 6px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )

    def set_color(self, hex_color: str):
        self._hex = hex_color
        self._update_style()


class PaletteSidebar(QWidget):
    """Left sidebar for palette scheme management — Origin-style compact."""

    scheme_changed = Signal(str)
    color_changed = Signal(int, str)       # index, new_hex
    color_count_changed = Signal(int)
    apply_to_current_clicked = Signal()
    save_as_new_clicked = Signal(str)     # name
    delete_scheme_clicked = Signal(str)   # name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title + scheme selector
        layout.addWidget(QLabel("🎨 配色方案"))
        self.scheme_combo = QComboBox()
        self.scheme_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}"
        )
        self.scheme_combo.currentTextChanged.connect(self.scheme_changed.emit)
        layout.addWidget(self.scheme_combo)

        # Gradient preview
        self.gradient_preview = QWidget()
        self.gradient_preview.setObjectName("GradientPreview")
        self.gradient_preview.setFixedHeight(20)
        self.gradient_preview.setStyleSheet(
            f"QWidget#GradientPreview {{ border: 1px solid #e2e8f0; border-radius: 6px; }}"
        )
        layout.addWidget(self.gradient_preview)

        # Color swatch grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        scroll_widget = QWidget()
        self.swatch_layout = QVBoxLayout(scroll_widget)
        self.swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.swatch_layout.setSpacing(4)
        self.swatch_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Color count selector
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("颜色数:"))
        self.count_combo = QComboBox()
        self.count_combo.addItems(["5", "6", "8", "10", "12", "16"])
        self.count_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}"
        )
        self.count_combo.currentTextChanged.connect(
            lambda t: self.color_count_changed.emit(int(t))
        )
        count_row.addWidget(self.count_combo, stretch=1)
        layout.addLayout(count_row)

        # Action buttons
        btn_apply = QPushButton("应用到当前")
        btn_apply.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.apply_to_current_clicked.emit)
        layout.addWidget(btn_apply)

        btn_save = QPushButton("另存为新方案")
        btn_save.setStyleSheet(BUTTON_STYLE)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._on_save_as_new)
        layout.addWidget(btn_save)

        btn_delete = QPushButton("🗑 删除方案")
        btn_delete.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._on_delete)
        layout.addWidget(btn_delete)

        # Internal state
        self._swatches: list[ColorSwatch] = []
        self._scheme_names: list[str] = []

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
        # Clear existing swatches
        for sw in self._swatches:
            sw.setParent(None)
        self._swatches.clear()

        # Remove the stretch
        while self.swatch_layout.count():
            item = self.swatch_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add swatch rows
        for i, (hex_color, name) in enumerate(zip(colors, segment_names)):
            row = QHBoxLayout()
            row.setSpacing(6)

            swatch = ColorSwatch(i, hex_color, name)
            swatch.color_clicked.connect(self._on_color_click)
            self._swatches.append(swatch)
            row.addWidget(swatch)

            lbl = QLabel(f"{hex_color}  {name}")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            row.addWidget(lbl, stretch=1)

            self.swatch_layout.addLayout(row)

        self.swatch_layout.addStretch()
        self._update_gradient(colors)

    def _on_color_click(self, index: int, _hex: str):
        color = QColorDialog.getColor()
        if color.isValid():
            new_hex = color.name()
            self._swatches[index].set_color(new_hex)
            self.color_changed.emit(index, new_hex)
            # Update gradient
            all_colors = [sw._hex for sw in self._swatches]
            self._update_gradient(all_colors)

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
            f"border: 1px solid #e2e8f0; border-radius: 6px; }}"
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
