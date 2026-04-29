from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from core.fitting import prepare_series, auto_tafel_fit
from core.types import PreparedSeries, TafelFit
from gui.widgets import parse_range_text, priority_label_to_key
from gui_qt.controllers.base import BaseAppController

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class FitWorker(QThread):
    """Background fitting worker using QThread.

    Runs auto_tafel_fit on the active segment and emits the results.
    """

    finished = Signal(object, object)  # PreparedSeries, TafelFit | None
    error = Signal(str)

    def __init__(
        self,
        channels: dict,
        pot_formula: str,
        cur_formula: str,
        e_eq: float,
        active_index: int,
        window_min: int,
        window_max: int,
        min_r2: float,
        fit_priority: str,
        eta_range,
        logj_range,
    ):
        super().__init__()
        self.channels = channels
        self.pot_formula = pot_formula
        self.cur_formula = cur_formula
        self.e_eq = e_eq
        self.active_index = active_index
        self.window_min = window_min
        self.window_max = window_max
        self.min_r2 = min_r2
        self.fit_priority = fit_priority
        self.eta_range = eta_range
        self.logj_range = logj_range

    def run(self) -> None:
        try:
            prepared = prepare_series(
                self.channels,
                potential_formula=self.pot_formula,
                current_formula=self.cur_formula,
                e_eq=self.e_eq,
                segment_index=self.active_index,
            )
            fit = auto_tafel_fit(
                prepared.eta,
                prepared.j,
                min_window=self.window_min,
                max_window=self.window_max,
                min_r2=self.min_r2,
                fit_priority=self.fit_priority,
                eta_range=self.eta_range,
                logj_range=self.logj_range,
            )
            self.finished.emit(prepared, fit)
        except Exception as exc:
            self.error.emit(str(exc))


class FittingController(BaseAppController):
    """Orchestrates background fitting via QThread worker.

    Reads parameters from ParamToolBar and formula panel, runs
    auto_tafel_fit in a worker thread, updates UI on completion.
    """

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FitWorker | None = None

    def run_fit(self) -> None:
        """Gather parameters and start background fitting."""
        app = self.app
        state = app._app_state
        channels = state.get("channels")
        if channels is None:
            return

        params = app.param_bar.get_params()

        # Parse e_eq
        try:
            e_eq = float(params.get("e_eq", "") or 0.0)
        except ValueError:
            app.status_bar.setText("E_eq 格式错误")
            return

        # Parse window range (integer range, minimum 2)
        try:
            window_min, window_max = parse_range_text(
                params.get("window_range", "") or "12-15",
                "窗口点数范围",
                integer=True,
                minimum=2,
            )
        except ValueError as exc:
            app.status_bar.setText(str(exc))
            return

        # Parse min_r2
        try:
            min_r2 = float(params.get("min_r2", "") or "0.95")
        except ValueError:
            app.status_bar.setText("最小 R² 格式错误")
            return

        # Parse optional ranges (allow empty)
        try:
            eta_range = parse_range_text(
                params.get("eta_range", ""), "η 范围", allow_empty=True,
            )
        except ValueError:
            eta_range = None
        try:
            logj_range = parse_range_text(
                params.get("logj_range", ""), "log(j) 范围", allow_empty=True,
            )
        except ValueError:
            logj_range = None

        # Convert fit priority label to key
        fit_priority = priority_label_to_key(
            params.get("fit_priority", "斜率更低优先")
        )

        pot_f, cur_f = app.formula_panel.get_formulas()
        active_index = state.get("active_segment_index", 0)
        segments = state.get("segments", [])
        if not segments:
            return

        app.status_bar.setText("正在拟合…")
        self._worker = FitWorker(
            channels,
            pot_f,
            cur_f,
            e_eq,
            active_index,
            window_min,
            window_max,
            min_r2,
            fit_priority,
            eta_range,
            logj_range,
        )
        self._worker.finished.connect(self._on_fit_finished)
        self._worker.error.connect(self._on_fit_error)
        self._worker.start()

    def _on_fit_finished(
        self, prepared: PreparedSeries, fit: TafelFit | None
    ) -> None:
        """Handle fitting completion: store results, update panels, render chart."""
        app = self.app

        # Store results in app state
        app._app_state["prepared"] = prepared
        app._app_state["fit"] = fit
        fit_by = {prepared.segment.index: fit} if fit else {}
        app._app_state["fit_by_segment"] = fit_by
        app._app_state["prepared_by_segment"] = {prepared.segment.index: prepared}

        # Update segment panel with fit results
        app.segment_panel.set_segments(
            app._app_state["segments"],
            app._app_state.get("active_segment_index", 0),
            app._app_state.get("segment_colors", {}),
            fit_by,
        )

        # Render chart via gui.rendering.render_figure (adapted for Qt
        # figure/canvas; draw() from gui.rendering is CTk-specific).
        from gui.rendering import render_figure

        active_index = app._app_state.get("active_segment_index", 0)
        p_map = app._app_state.get("prepared_by_segment") or {
            prepared.segment.index: prepared
        }
        f_map = app._app_state.get("fit_by_segment") or fit_by
        render_figure(
            app,
            app.chart.fig,
            display_indices=[active_index],
            active_index=active_index,
            prepared_by_segment=p_map,
            fit_by_segment=f_map,
        )
        app.chart.canvas.draw_idle()

        if fit:
            app.status_bar.setText(
                f"第{prepared.segment.index + 1}段拟合完成: "
                f"{fit.slope_mv_per_dec:.2f} mV/dec, "
                f"R²={fit.r2:.4f}"
            )
        else:
            app.status_bar.setText(
                f"第{prepared.segment.index + 1}段拟合失败"
            )

    def _on_fit_error(self, msg: str) -> None:
        """Handle fitting errors."""
        self.app.status_bar.setText(f"拟合错误: {msg[:60]}")
