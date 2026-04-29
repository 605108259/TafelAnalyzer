from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from gui_qt.theme import BG_CARD, BORDER


class ChartArea(QWidget):
    """Central matplotlib chart area with dual plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # matplotlib figure
        self.fig = Figure(figsize=(10.8, 6.6), dpi=100)
        self.fig.set_facecolor(BG_CARD)
        self.fig.patch.set_facecolor(BG_CARD)

        # Canvas
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet(f"background: {BG_CARD};")
        layout.addWidget(self.canvas, stretch=1)

        # Store for external code that needs to access the figure
        self.axes: list = []

    def clear_figure(self) -> None:
        self.fig.clear()
        self.axes = []
        self.canvas.draw_idle()
