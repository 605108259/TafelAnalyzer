from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QScrollArea
from PySide6.QtCore import Qt

from gui_qt.theme import BG_CARD, TEXT_SECONDARY, TEXT_PRIMARY, ACCENT


class PaletteWorkspace(QWidget):
    """Right-side large color grid for Origin-style palette editing."""

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

    def set_scheme(self, name: str, colors: list[str], segment_names: list[str]) -> None:
        """Show large swatches for the selected scheme."""
        self.scheme_label.setText(f"方案: {name}  ({len(colors)} 色)")

        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add swatches in a responsive grid
        cols = 4
        for i, (hex_color, seg_name) in enumerate(zip(colors, segment_names)):
            swatch = QWidget()
            swatch.setFixedSize(120, 100)
            swatch.setStyleSheet(
                f"QWidget {{ background: {hex_color}; border-radius: 12px; "
                f"border: 2px solid #e2e8f0; }}"
            )
            swatch.setToolTip(f"{seg_name}: {hex_color}")

            label = QLabel(f"{seg_name}\n{hex_color}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {'#0f172a' if _is_light(hex_color) else '#ffffff'}; "
                f"font-size: 11px; font-weight: 600; background: transparent; border: none;"
            )

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(swatch, row, col)
            # Overlay text on swatch
            label.setParent(swatch)
            label.setGeometry(4, 30, 112, 40)


def _is_light(hex_color: str) -> bool:
    """Return True if the color is light (for text contrast)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance > 150
