from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QScrollArea, QPushButton, QColorDialog
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import BG_CARD, TEXT_SECONDARY, TEXT_PRIMARY


class ClickableSwatch(QPushButton):
    """A large color swatch button in the palette workspace."""

    clicked_with_color = Signal(int, str)  # index, current_hex

    def __init__(self, index: int, hex_color: str, seg_name: str):
        super().__init__()
        self._index = index
        self._hex = hex_color
        self.setFixedSize(120, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{seg_name}: {hex_color} — 点击更换颜色")
        self._update_style()
        self.clicked.connect(self._on_click)

        # Label overlay
        label = QLabel(f"{seg_name}\n{hex_color}", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"color: {'#0f172a' if _is_light(hex_color) else '#ffffff'}; "
            f"font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        label.setGeometry(4, 30, 112, 40)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)

    def _update_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._hex}; border-radius: 12px; "
            f"border: 2px solid #e2e8f0; }}"
            f"QPushButton:hover {{ border-color: #2563eb; }}"
        )

    def _on_click(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self._hex = color.name()
            self._update_style()
            self.clicked_with_color.emit(self._index, self._hex)


class PaletteWorkspace(QWidget):
    """Right-side large color grid for Origin-style palette editing."""

    swatch_clicked = Signal(int, str)  # index, new_hex

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("配色方案编辑")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Subtitle
        self.scheme_label = QLabel("选择一个配色方案")
        self.scheme_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        layout.addWidget(self.scheme_label)

        # Color grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(12)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, stretch=1)

        self._swatches: list[ClickableSwatch] = []

    def set_scheme(self, name: str, colors: list[str], segment_names: list[str]) -> None:
        """Show large swatches for the selected scheme."""
        self.scheme_label.setText(f"方案: {name}  ({len(colors)} 色)")

        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._swatches.clear()

        # Add swatches in a responsive grid
        cols = 4
        for i, (hex_color, seg_name) in enumerate(zip(colors, segment_names)):
            swatch = ClickableSwatch(i, hex_color, seg_name)
            swatch.clicked_with_color.connect(self.swatch_clicked.emit)
            self._swatches.append(swatch)

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(swatch, row, col)


def _is_light(hex_color: str) -> bool:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance > 150
