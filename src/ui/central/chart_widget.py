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
        self._legend_bg: memoryview | None = None  # blit background during legend drag

        self.fig.canvas.mpl_connect("button_press_event", self._on_fig_click)
        self.fig.canvas.mpl_connect("button_release_event", self._on_fig_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_fig_motion)
        self.fig.canvas.mpl_connect("scroll_event", self._on_fig_scroll)
        # Double-click on axis title/label → rename
        self.fig.canvas.mpl_connect("button_press_event", self._on_axis_label_dblclick)

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
        """窗口尺寸稳定后触发 — Agg 后端自动处理缩放，无需 draw_idle。"""
        self.resized_stable.emit()

    def _find_label_artist(self, event) -> object | None:
        """Return the axis label artist at *event* position, or None."""
        if event.x is None or event.y is None:
            return None
        try:
            renderer = self.fig.canvas.get_renderer()
        except Exception:
            return None
        for ax in self.fig.axes:
            for artist in (ax.title, ax.xaxis.label, ax.yaxis.label):
                try:
                    bbox = artist.get_window_extent(renderer)
                    if bbox is not None and bbox.contains(event.x, event.y):
                        return artist
                except Exception:
                    continue
        return None

    def _on_fig_click(self, event) -> None:
        legend_drag = self._legend_drag_candidate(event)
        if legend_drag is not None:
            self._legend_drag = legend_drag
            for ax in self.fig.axes:
                leg = ax.get_legend()
                if leg is not None:
                    leg.set_animated(True)
            self.canvas.draw()
            self._legend_bg = self.canvas.copy_from_bbox(self.fig.bbox)
            try:
                if not self.fig.canvas.widgetlock.locked():
                    self.fig.canvas.widgetlock(self)
            except Exception:
                pass
            return
        if event.inaxes is None and self._find_label_artist(event) is None:
            self.clicked_outside_axes.emit()

    def _on_fig_release(self, event) -> None:
        if self._legend_drag is not None:
            # blit cleanup: unset animated flags, then full redraw
            for ax in self.fig.axes:
                leg = ax.get_legend()
                if leg is not None:
                    leg.set_animated(False)
            self._legend_bg = None
            self._legend_drag = None
            try:
                if self.fig.canvas.widgetlock.isowner(self):
                    self.fig.canvas.widgetlock.release(self)
            except Exception:
                pass
            self.canvas.draw_idle()
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
            try:
                if hasattr(legend, "set_loc"):
                    legend.set_loc("lower left")
                else:
                    legend._loc = 3
            except Exception:
                pass
            legend.set_bbox_to_anchor((float(anchor[0]), float(anchor[1])), transform=axis.transAxes)
            # blit: restore background and redraw only legends
            if self._legend_bg is not None:
                self.canvas.restore_region(self._legend_bg)
                for ax in self.fig.axes:
                    leg = ax.get_legend()
                    if leg is not None:
                        ax.draw_artist(leg)
                self.canvas.blit(self.fig.bbox)
        except Exception:
            return

    def _on_fig_scroll(self, event) -> None:
        self.interaction_finished.emit()

    def _on_axis_label_dblclick(self, event) -> None:
        """Double-click axis title or label to rename."""
        if not getattr(event, "dblclick", False):
            return
        artist = self._find_label_artist(event)
        if artist is not None:
            self._rename_axis_text(artist)

    def _axis_label_key(self, artist) -> str | None:
        """Return a stable state key for *artist*, or None."""
        if self.fig.axes is None:
            return None
        # Find which axis this artist belongs to
        for ax_idx, ax in enumerate(self.fig.axes):
            if artist is ax.title:
                label_type = "title"
            elif artist is ax.xaxis.label:
                label_type = "xlabel"
            elif artist is ax.yaxis.label:
                label_type = "ylabel"
            else:
                continue
            mode = "comp" if getattr(self.window(), '_app_state', {}).get("active_chart_mode") == "comparison" else "single"
            return f"{mode}_ax{ax_idx}_{label_type}"
        return None

    def _rename_axis_text(self, artist) -> None:
        from PySide6.QtWidgets import QInputDialog
        old_text = artist.get_text()
        new_text, ok = QInputDialog.getText(
            self, "重命名坐标轴", "新名称:", text=old_text,
        )
        if ok and new_text.strip():
            artist.set_text(new_text.strip())
            # Persist to app state + disk so all files and sessions keep the name
            key = self._axis_label_key(artist)
            if key is not None:
                win = self.window()
                if hasattr(win, '_app_state'):
                    overrides = win._app_state.setdefault("axis_label_overrides", {})
                    overrides[key] = new_text.strip()
                    try:
                        from ui.settings import save_app_settings
                        save_app_settings(win)
                    except Exception:
                        pass
            self.canvas.draw_idle()

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

    def close_figure(self) -> None:
        import matplotlib.pyplot as plt
        try:
            self.fig.clear()
        except Exception:
            pass
        try:
            plt.close(self.fig)
        except Exception:
            pass
        self.axes = []
        self.fig = None

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
