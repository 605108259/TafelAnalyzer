from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QThread, Signal, Qt

from core.fitting import (
    prepare_series, prepare_full_series, prepare_series_from_full,
    auto_tafel_fit, manual_tafel_fit, build_segment_infos,
)
from core.types import PreparedSeries, TafelFit
from core.utils import parse_range_text, priority_label_to_key
from ui.controllers.base import BaseAppController
from ui.controllers.worker_utils import stop_worker

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


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
        precomputed_segments=None,
        prepared_cache=None,
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
        self.precomputed_segments = precomputed_segments
        self.prepared_cache = dict(prepared_cache or {})
        self.generation: int | None = None

    def run(self) -> None:
        # Snapshot all fields set from main thread before any work.
        channels = dict(self.channels)
        pot_formula = self.pot_formula
        cur_formula = self.cur_formula
        e_eq = self.e_eq
        selected_indices = list(self.selected_indices)
        window_min = self.window_min
        window_max = self.window_max
        min_r2 = self.min_r2
        fit_priority = self.fit_priority
        eta_range = self.eta_range
        logj_range = self.logj_range
        precomputed_segments = self.precomputed_segments
        prepared_cache = dict(self.prepared_cache)
        try:
            prepared_map = {}
            fit_map = {}
            error_map = {}

            # ━━ Separate cached vs uncached segments ━━
            uncached_indices: list[int] = []
            for seg_idx in selected_indices:
                prepared = prepared_cache.get(seg_idx)
                if prepared is not None:
                    prepared_map[seg_idx] = prepared
                else:
                    uncached_indices.append(seg_idx)

            # ━━ Precompute full-data once for all uncached segments ━━
            if uncached_indices:
                try:
                    full_data, all_segments = prepare_full_series(
                        channels,
                        potential_formula=pot_formula,
                        current_formula=cur_formula,
                        e_eq=e_eq,
                        precomputed_segments=precomputed_segments,
                    )
                except Exception as exc:
                    for seg_idx in uncached_indices:
                        error_map[seg_idx] = str(exc)
                    self.finished.emit(prepared_map, fit_map, error_map)
                    return

                for seg_idx in uncached_indices:
                    try:
                        segment = all_segments[seg_idx]
                        prepared = prepare_series_from_full(full_data, segment)
                        prepared_map[seg_idx] = prepared
                    except Exception as exc:
                        error_map[seg_idx] = str(exc)

            # ━━ Fit all segments (parallel) ━━
            pending_indices = [
                idx for idx in selected_indices if idx not in error_map
            ]
            if pending_indices:
                max_workers = min(8, os.cpu_count() or 4, len(pending_indices))

                def _fit_one(seg_idx: int):
                    prepared = prepared_map[seg_idx]
                    fit = auto_tafel_fit(
                        prepared.eta, prepared.j,
                        min_window=window_min, max_window=window_max,
                        min_r2=min_r2, fit_priority=fit_priority,
                        eta_range=eta_range, logj_range=logj_range,
                    )
                    return seg_idx, fit, None

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(_fit_one, idx): idx
                        for idx in pending_indices
                    }
                    for future in as_completed(futures):
                        try:
                            seg_idx, fit, _exc = future.result()
                            fit_map[seg_idx] = fit
                        except Exception as exc:
                            error_map[futures[future]] = str(exc)

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

    def cancel_running(self) -> None:
        stop_worker(self._worker)
        self._worker = None

    def _prepared_cache_key(
        self,
        *,
        path,
        potential_formula: str,
        current_formula: str,
        e_eq: float,
        segment_index: int,
    ) -> tuple:
        from core.cache import file_fingerprint

        return (
            "prepared-eq-minus-e-v1",
            file_fingerprint(path),
            potential_formula,
            current_formula,
            round(float(e_eq), 12),
            int(segment_index),
        )

    def _prepared_from_cache(
        self,
        *,
        path,
        potential_formula: str,
        current_formula: str,
        e_eq: float,
        segment_index: int,
    ):
        key = self._prepared_cache_key(
            path=path,
            potential_formula=potential_formula,
            current_formula=current_formula,
            e_eq=e_eq,
            segment_index=segment_index,
        )
        return self.app._app_state.setdefault("prepared_cache", {}).get(key)

    def _remember_prepared(self, *, path, prepared) -> None:
        key = self._prepared_cache_key(
            path=path,
            potential_formula=prepared.potential_formula,
            current_formula=prepared.current_formula,
            e_eq=float(prepared.e_eq),
            segment_index=int(prepared.segment.index),
        )
        cache = self.app._app_state.setdefault("prepared_cache", {})
        cache[key] = prepared
        if len(cache) > 512:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)

    def run_fit(self, *, force: bool = False) -> None:
        """Gather parameters and start background fitting for all selected segments."""
        app = self.app
        state = app._app_state
        channels = state.get("channels")
        if channels is None:
            return

        pot_f, cur_f = app.toolbar.get_formulas()
        if not pot_f or not cur_f:
            app.status_bar.setText("请先在公式栏选择电位和电流通道")
            return

        segments = state.get("segments", [])
        if not segments:
            try:
                segment_infos = build_segment_infos(channels, pot_f)
            except Exception as exc:
                app.status_bar.setText(f"电位通道/公式无法分段: {exc}")
                return
            scheme_name = app.state.palette.active_name
            segment_colors = {
                segment.index: app.state.palette.color_at(segment.index, scheme_name)
                for segment in segment_infos
            }
            state["_precomputed_segments"] = segment_infos
            app.state.analysis.apply_loaded_file(
                channels=channels,
                segment_infos=segment_infos,
                segment_colors=segment_colors,
            )
            app.views.refresh_segments(rebuild=True)
            segments = state.get("segments", [])

        selected_indices = [int(index) for index in state.get("selected_segment_indices", [])]
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
            window_range = parse_range_text(
                params.get("window_range", "") or "12-15",
                "窗口点数范围",
                integer=True,
                minimum=2,
            )
            if window_range is None:
                raise ValueError("窗口点数范围不能为空")
            window_min, window_max = int(window_range[0]), int(window_range[1])
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

        path = app.state.files.current_path
        if path is not None:
            from core.cache import make_result_cache_key

            cache_key = make_result_cache_key(
                tdms_path=path,
                potential_formula=pot_f,
                current_formula=cur_f,
                e_eq=e_eq,
                selected_segment_indices=tuple(selected_indices),
                min_window=window_min,
                max_window=window_max,
                eta_range=eta_range,
                logj_range=logj_range,
                min_r2=min_r2,
                fit_priority=fit_priority,
            )
            if not force and hasattr(app, "files"):
                entry = app.files.result_cache_entry(cache_key)
                if entry is not None and app.files.restore_result_cache_entry(
                    cache_key,
                    entry,
                    status="已从当前项目缓存恢复拟合结果",
                ):
                    return
        prepared_cache = {}
        if path is not None:
            for segment_index in selected_indices:
                prepared = self._prepared_from_cache(
                    path=path,
                    potential_formula=pot_f,
                    current_formula=cur_f,
                    e_eq=e_eq,
                    segment_index=int(segment_index),
                )
                if prepared is not None:
                    prepared_cache[int(segment_index)] = prepared

        # Clean up previous worker
        stop_worker(self._worker)

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
            precomputed_segments=state.get("_precomputed_segments"),
            prepared_cache=prepared_cache,
        )
        generation = app.state.operations.generation
        self._worker.generation = generation
        self._worker.finished.connect(self._on_fit_finished_from_worker)
        self._worker.error.connect(self._on_fit_error_from_worker)
        self._worker.start()

    def _on_fit_finished_from_worker(self, prepared_map, fit_map, error_map) -> None:
        worker = cast(FitWorker | None, self.sender())
        if worker is None:
            return
        self._on_fit_finished(prepared_map, fit_map, error_map, worker.generation)

    def _on_fit_error_from_worker(self, msg) -> None:
        worker = cast(FitWorker | None, self.sender())
        if worker is None:
            return
        if not self.app.state.operations.is_current(worker.generation):
            return
        self._on_fit_error(msg)

    def _on_fit_finished(
        self, prepared_map: dict, fit_map: dict, error_map: dict, generation: int | None = None
    ) -> None:
        """Handle fitting completion: store results, update panels, render chart."""
        app = self.app
        if not app.state.operations.is_current(generation):
            return
        regions = app._app_state.setdefault("manual_fit_regions", {})
        for segment_index in set(prepared_map) | set(fit_map) | set(error_map):
            regions.pop(int(segment_index), None)
        active_prepared = app.state.analysis.merge_fit_results(
            prepared_map=prepared_map,
            fit_map=fit_map,
            error_map=error_map,
        )
        path = app.state.files.current_path
        if path is not None:
            for prepared in prepared_map.values():
                self._remember_prepared(path=path, prepared=prepared)

        app.views.refresh_segments()
        if active_prepared is not None:
            app.views.render_single()
            from core.rendering import reset_origin_view
            reset_origin_view(app)
        if hasattr(app, "files"):
            app.files.autosave_project_history()

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
        app.state.interaction.enable_manual(
            path=app.state.files.current_path,
            generation=app.state.operations.generation,
        )
        app.status_bar.setText("已进入手动框选模式，在右侧 Tafel 图上框选拟合区域")
        if app._app_state.get("prepared") is not None:
            from core.rendering import refresh_selector
            refresh_selector(app)
        from PySide6.QtGui import QCursor
        app.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def disable_manual_mode(self) -> None:
        app = self.app
        app.state.interaction.disable_manual()
        from PySide6.QtGui import QCursor
        app.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        from core.rendering import destroy_selector
        destroy_selector(app)
        if hasattr(app, "toolbar"):
            app.toolbar.clear_nav_mode()

    def on_manual_select(self, eclick, erelease) -> None:
        """Handle RectangleSelector callback for manual fitting mode."""
        app = self.app
        if app._app_state.get("prepared") is None:
            return
        if not app.state.interaction.manual_is_current(
            path=app.state.files.current_path,
            generation=app.state.operations.generation,
        ):
            return
        current_ax = app._app_state.get("ax_tafel")
        if current_ax is None or eclick.inaxes is not current_ax or erelease.inaxes is not current_ax:
            return
        coords = (eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata)
        if any(v is None for v in coords):
            return
        try:
            from core.rendering import capture_axes_limits, draw, refresh_selector

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

            active_index = int(app._app_state.get("active_segment_index", 0))
            prepared = app._app_state.get("prepared_by_segment", {}).get(active_index)
            if prepared is None:
                try:
                    e_eq = float(params.get("e_eq", "") or 0.0)
                except ValueError:
                    app.status_bar.setText("E_eq 格式错误")
                    return
                pot_f, cur_f = app.toolbar.get_formulas()
                path = app.state.files.current_path
                if path is not None:
                    prepared = self._prepared_from_cache(
                        path=path,
                        potential_formula=pot_f,
                        current_formula=cur_f,
                        e_eq=e_eq,
                        segment_index=active_index,
                    )
                if prepared is None:
                    prepared = prepare_series(
                        app._app_state["channels"],
                        potential_formula=pot_f,
                        current_formula=cur_f,
                        e_eq=e_eq,
                        segment_index=active_index,
                        precomputed_segments=app._app_state.get("_precomputed_segments"),
                    )
                    if path is not None:
                        self._remember_prepared(path=path, prepared=prepared)
                app._app_state.setdefault("prepared_by_segment", {})[active_index] = prepared
            app._app_state["prepared"] = prepared
            app._app_state["fit"] = app._app_state.get("fit_by_segment", {}).get(active_index)
            fit = manual_tafel_fit(
                prepared.eta, prepared.j,
                x_min=float(eclick.xdata), x_max=float(erelease.xdata),
                y_min=float(eclick.ydata), y_max=float(erelease.ydata),
                eta_range=eta_range, logj_range=logj_range,
                min_r2=min_r2,
            )
            app._app_state.setdefault("manual_fit_regions", {})[active_index] = {
                "x_min": min(float(eclick.xdata), float(erelease.xdata)),
                "x_max": max(float(eclick.xdata), float(erelease.xdata)),
                "y_min": min(float(eclick.ydata), float(erelease.ydata)),
                "y_max": max(float(eclick.ydata), float(erelease.ydata)),
            }
            app.state.analysis.apply_manual_fit(segment_index=active_index, fit=fit)

            draw(app, prepared, fit, preserve_view_state=limits)
            app.status_bar.setText(
                f"手动拟合完成: {fit.slope_mv_per_dec:.2f} mV/dec, R²={fit.r2:.4f}"
            )
            if hasattr(app, "files"):
                app.files.autosave_project_history()
            # Keep manual mode active for continuous selection
            refresh_selector(app)
        except Exception as exc:
            app.status_bar.setText(f"手动拟合失败: {exc}")
            # Keep manual mode active so user can try again
            from core.rendering import refresh_selector as rs
            rs(app)

    def _on_fit_error(self, msg: str) -> None:
        """Handle fitting errors."""
        self.app.status_bar.setText(f"拟合错误: {msg[:60]}")
