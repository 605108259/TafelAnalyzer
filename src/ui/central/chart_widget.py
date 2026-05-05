from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal

from gui_qt.theme import BG_CARD, BORDER


class ChartArea(QWidget):
    """Central matplotlib chart area with dual plots."""

    clicked_outside_axes = Signal()

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

        # Hidden NavigationToolbar2QT for programmatic zoom/pan/home/back/forward
        self._nav_toolbar = NavigationToolbar2QT(self.canvas, self)
        self._nav_toolbar.hide()

        # Store for external code that needs to access the figure
        self.axes: list = []

        self.fig.canvas.mpl_connect("button_press_event", self._on_fig_click)

    def _on_fig_click(self, event) -> None:
        if event.inaxes is None and self._nav_toolbar.mode:
            self.clicked_outside_axes.emit()

    def clear_figure(self) -> None:
        self.fig.clear()
        self.axes = []
        self.canvas.draw_idle()

    def cancel_nav_modes(self) -> None:
        mode = self._nav_toolbar.mode
        if mode == "pan/zoom":
            self._nav_toolbar.pan()
        elif mode == "zoom rect":
            self._nav_toolbar.zoom()

    @property
    def nav_mode(self) -> str:
        return self._nav_toolbar.mode

    def nav_home(self) -> None:
        self.cancel_nav_modes()
        self._nav_toolbar.home()

    def nav_back(self) -> None:
        self.cancel_nav_modes()
        self._nav_toolbar.back()

    def nav_forward(self) -> None:
        self.cancel_nav_modes()
        self._nav_toolbar.forward()

    def nav_zoom(self) -> None:
        self.cancel_nav_modes()
        self._nav_toolbar.zoom()

    def nav_pan(self) -> None:
        self.cancel_nav_modes()
        self._nav_toolbar.pan()
