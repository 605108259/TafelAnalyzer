from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt import NavigationToolbar2QT

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal, QTimer

from ui.theme import BG_CARD


class ChartArea(QWidget):
    """Central matplotlib chart area with dual plots."""

    clicked_outside_axes = Signal()
    interaction_finished = Signal()
    # 窗口大小变化且稳定后发出，供外部按需重绘
    resized_stable = Signal()

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
        self._legend_drag: dict | None = None

        self.fig.canvas.mpl_connect("button_press_event", self._on_fig_click)
        self.fig.canvas.mpl_connect("button_release_event", self._on_fig_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_fig_motion)
        self.fig.canvas.mpl_connect("scroll_event", self._on_fig_scroll)

        # Resize debounce timer — 防止窗口拖拽时频繁全量重绘
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)  # 150ms 防抖
        self._resize_timer.timeout.connect(self._on_resize_stable)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # 每次 resize 都重置计时器，直到窗口停止拖拽才触发稳定信号
        self._resize_timer.start()

    def _on_resize_stable(self) -> None:
        """窗口尺寸稳定后触发，仅 draw_idle 不做全量重渲。"""
        self.canvas.draw_idle()
        self.resized_stable.emit()

    def _on_fig_click(self, event) -> None:
        legend_drag = self._legend_drag_candidate(event)
        if legend_drag is not None:
            self._legend_drag = legend_drag
            try:
                if not self.fig.canvas.widgetlock.locked():
                    self.fig.canvas.widgetlock(self)
            except Exception:
                pass
            return
        if event.inaxes is None:
            self.clicked_outside_axes.emit()

    def _on_fig_release(self, event) -> None:
        if self._legend_drag is not None:
            self._legend_drag = None
            try:
                if self.fig.canvas.widgetlock.isowner(self):
                    self.fig.canvas.widgetlock.release(self)
            except Exception:
                pass
            self.interaction_finished.emit()
            return
        self.interaction_finished.emit()

    def _on_fig_motion(self, event) -> None:
        drag = self._legend_drag
        if drag is None or event.x is None or event.y is None:
            return
        legend = drag.get("legend")
        axis = drag.get("axis")
        offset = drag.get("offset", (0.0, 0.0))
        if legend is None or axis is None:
            return
        try:
            x0 = float(event.x) - float(offset[0])
            y0 = float(event.y) - float(offset[1])
            anchor = axis.transAxes.inverted().transform((x0, y0))
            if hasattr(legend, "set_loc"):
                legend.set_loc("lower left")
            else:
                legend._loc = 3
            legend.set_bbox_to_anchor((float(anchor[0]), float(anchor[1])), transform=axis.transAxes)
            self.canvas.draw_idle()
        except Exception:
            return

    def _on_fig_scroll(self, event) -> None:
        self.interaction_finished.emit()

    def _legend_drag_candidate(self, event) -> dict | None:
        if event.x is None or event.y is None:
            return None
        try:
            renderer = self.fig.canvas.get_renderer()
            for axis in reversed(self.fig.axes):
                legend = axis.get_legend()
                if legend is None:
                    continue
                extent = legend.get_window_extent(renderer=renderer)
                if extent.contains(event.x, event.y):
                    return {
                        "legend": legend,
                        "axis": axis,
                        "offset": (float(event.x) - float(extent.x0), float(event.y) - float(extent.y0)),
                    }
        except Exception:
            return None
        return None

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
