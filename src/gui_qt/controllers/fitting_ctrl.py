from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal, Qt

from core.fitting import prepare_series, auto_tafel_fit, manual_tafel_fit
from core.types import PreparedSeries, TafelFit
from core.utils import parse_range_text, priority_label_to_key
from gui_qt.controllers.base import BaseAppController

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class FitWorker(QThread):
    """Background fitting worker using QThread.

    Runs auto_tafel_fit on ALL selected segments and emits the results.
    """

    finished = Signal(object, object, object)  # prepared_map, fit_map, error_map
    error = Signal(str)

    def __init__(
        self,
        channels: dict,
        pot_formula: str,
        cur_formula: str,
        e_eq: float,
        selected_indices: list[int],
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
        self.selected_indices = selected_indices
        self.window_min = window_min
        self.window_max = window_max
        self.min_r2 = min_r2
        self.fit_priority = fit_priority
        self.eta_range = eta_range
        self.logj_range = logj_range

    def run(self) -> None:
        try:
            prepared_map = {}
            fit_map = {}
            error_map = {}
            for seg_idx in self.selected_indices:
                try:
                    prepared = prepare_series(
                        self.channels,
                        potential_formula=self.pot_formula,
                        current_formula=self.cur_formula,
                        e_eq=self.e_eq,
                        segment_index=seg_idx,
                    )
                    prepared_map[seg_idx] = prepared
                except Exception as exc:
                    error_map[seg_idx] = str(exc)
                    continue
                try:
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
                    fit_map[seg_idx] = fit
                except Exception as exc:
                    error_map[seg_idx] = str(exc)
            self.finished.emit(prepared_map, fit_map, error_map)
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
        """Gather parameters and start background fitting for all selected segments."""
        app = self.app
        state = app._app_state
        channels = state.get("channels")
        if channels is None:
            return

        segments = state.get("segments", [])
        if not segments:
            return

        selected_indices = list(state.get("selected_segment_indices", []))
        if not selected_indices:
            return

        params = app.toolbar.get_params()

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

        pot_f, cur_f = app.toolbar.get_formulas()

        # Clean up previous worker
        if self._worker and self._worker.isRunning():
            self._worker.finished.disconnect()
            self._worker.error.disconnect()
            self._worker.quit()
            self._worker.wait(3000)

        app.status_bar.setText(f"正在拟合 {len(selected_indices)} 个分段…")
        self._worker = FitWorker(
            channels,
            pot_f,
            cur_f,
            e_eq,
            selected_indices,
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
        self, prepared_map: dict, fit_map: dict, error_map: dict
    ) -> None:
        """Handle fitting completion: store results, update panels, render chart."""
        app = self.app
        active_index = app._app_state.get("active_segment_index", 0)

        # Merge results into state
        prev_prepared = dict(app._app_state.get("prepared_by_segment", {}))
        prev_prepared.update(prepared_map)
        app._app_state["prepared_by_segment"] = prev_prepared

        prev_fit = dict(app._app_state.get("fit_by_segment", {}))
        prev_fit.update(fit_map)
        app._app_state["fit_by_segment"] = prev_fit

        prev_err = dict(app._app_state.get("fit_error_by_segment", {}))
        prev_err.update(error_map)
        app._app_state["fit_error_by_segment"] = prev_err

        # Set primary prepared/fit from active segment
        active_prepared = prepared_map.get(active_index)
        if active_prepared is None and prepared_map:
            active_prepared = next(iter(prepared_map.values()))
        app._app_state["prepared"] = active_prepared
        app._app_state["fit"] = fit_map.get(
            active_prepared.segment.index if active_prepared else active_index
        )

        # Update segment panel with fit results
        app.file_segment_panel.update_segment_state(
            active_index=active_index,
            checked_indices=set(app._app_state.get("selected_segment_indices", [])),
            colors=app._app_state.get("segment_colors", {}),
            fit_by_segment=app._app_state.get("fit_by_segment", {}),
        )

        # Render chart
        from gui.rendering import draw

        if active_prepared is not None:
            draw(app, active_prepared, fit_map.get(active_prepared.segment.index))

        # Status summary
        success_count = len(fit_map)
        fail_count = len(error_map)
        total = success_count + fail_count
        if total == 0:
            app.status_bar.setText("拟合完成（无有效分段）")
        elif fail_count == 0:
            first_fit = next(iter(fit_map.values()))
            app.status_bar.setText(
                f"{total} 段拟合完成，当前: "
                f"{first_fit.slope_mv_per_dec:.2f} mV/dec, R²={first_fit.r2:.4f}"
            )
        else:
            app.status_bar.setText(
                f"拟合完成: {success_count} 成功, {fail_count} 失败"
            )

    def enable_manual_mode(self) -> None:
        """Switch to manual fitting mode."""
        app = self.app
        if app._app_state.get("channels") is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(app, "提示", "请先选择并加载数据文件")
            app.toolbar.clear_nav_mode()
            return
        if app._app_state.get("_fitting_lock"):
            return
        app._app_state["manual_mode"] = True
        app.status_bar.setText("已进入手动框选模式，在右侧 Tafel 图上框选拟合区域")
        if app._app_state.get("prepared") is not None:
            from gui.rendering import refresh_selector
            refresh_selector(app)
        from PySide6.QtGui import QCursor
        app.canvas.setCursor(QCursor(Qt.CrossCursor))

    def disable_manual_mode(self) -> None:
        app = self.app
        app._app_state["manual_mode"] = False
        from PySide6.QtGui import QCursor
        app.canvas.setCursor(QCursor(Qt.ArrowCursor))
        from gui.rendering import refresh_selector
        refresh_selector(app)
        if hasattr(app, "toolbar"):
            app.toolbar.clear_nav_mode()

    def on_manual_select(self, eclick, erelease) -> None:
        """Handle RectangleSelector callback for manual fitting mode."""
        app = self.app
        if not app._app_state.get("manual_mode") or app._app_state.get("prepared") is None:
            return
        coords = (eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata)
        if any(v is None for v in coords):
            return
        try:
            from gui.rendering import capture_axes_limits, draw, refresh_selector

            limits = capture_axes_limits(app)
            params = app.toolbar.get_params()
            min_r2 = float(params.get("min_r2", "0.95") or "0.95")
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

            prepared = app._app_state["prepared"]
            fit = manual_tafel_fit(
                prepared.eta, prepared.j,
                x_min=float(eclick.xdata), x_max=float(erelease.xdata),
                y_min=float(eclick.ydata), y_max=float(erelease.ydata),
                eta_range=eta_range, logj_range=logj_range,
                min_r2=min_r2,
            )
            active_index = int(app._app_state.get(
                "active_segment_index", prepared.segment.index
            ))
            app._app_state["fit_by_segment"][active_index] = fit
            app._app_state["fit_error_by_segment"].pop(active_index, None)
            app._app_state["fit"] = fit

            draw(app, prepared, fit, preserve_view_state=limits)
            app.status_bar.setText(
                f"手动拟合完成: {fit.slope_mv_per_dec:.2f} mV/dec, R²={fit.r2:.4f}"
            )
            # Keep manual mode active for continuous selection
            refresh_selector(app)
        except Exception as exc:
            app.status_bar.setText(f"手动拟合失败: {exc}")
            # Keep manual mode active so user can try again
            from gui.rendering import refresh_selector as rs
            rs(app)

    def _on_fit_error(self, msg: str) -> None:
        """Handle fitting errors."""
        self.app.status_bar.setText(f"拟合错误: {msg[:60]}")
