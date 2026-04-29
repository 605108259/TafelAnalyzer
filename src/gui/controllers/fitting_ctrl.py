from __future__ import annotations

import threading
import traceback
from typing import TYPE_CHECKING, Callable

from tkinter import messagebox

from core.fitting import auto_tafel_fit, manual_tafel_fit, prepare_series, build_segment_infos
from core.formula import normalize_formula
from core.types import CURRENT_PREFERRED_NAMES, POTENTIAL_PREFERRED_NAMES, PreparedSeries, TafelFit
from gui.widgets import parse_range_text, priority_label_to_key
from gui import rendering as r
from gui import cache as c
from gui import settings
from gui.logger import log_info, log_error

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


class FittingController:
    def __init__(self, app: TafelAnalyzerApp):
        self.app = app

    def collect_inputs(self) -> dict:
        app = self.app
        if app._app_state["channels"] is None:
            raise ValueError("请先加载数据文件")
        min_window, max_window = parse_range_text(
            app.entry_window_range.get(), "窗口点数范围", integer=True, minimum=2,
        )
        e_eq = float(app.entry_eeq.get().strip() or "0")
        min_r2 = float(app.entry_min_r2.get().strip() or "0")
        if min_r2 > 1.0:
            raise ValueError("最小 R² 不能大于 1")
        active_segment_index = int(app._app_state.get("active_segment_index", 0))
        selected_segment_indices = list(app._app_state.get("selected_segment_indices", []))
        processing_segment_indices = (
            sorted(set(selected_segment_indices + [active_segment_index]))
            if app._app_state["segments"] else []
        )
        eta_range = parse_range_text(app.entry_eta_range.get(), "η 范围", allow_empty=True)
        logj_range = parse_range_text(app.entry_logj_range.get(), "log(j) 范围", allow_empty=True)
        return {
            "potential_formula": app.entry_potential_formula.get().strip(),
            "current_formula": app.entry_current_formula.get().strip(),
            "export_name": app.entry_export_name.get().strip(),
            "e_eq": e_eq,
            "active_segment_index": active_segment_index,
            "selected_segment_indices": selected_segment_indices,
            "processing_segment_indices": processing_segment_indices,
            "min_window": min_window,
            "max_window": max_window,
            "eta_range": eta_range,
            "logj_range": logj_range,
            "min_r2": min_r2,
            "fit_priority": priority_label_to_key(app.combo_fit_priority.get()),
        }

    def prepare_current_series(self) -> PreparedSeries:
        inputs = self.collect_inputs()
        return prepare_series(
            self.app._app_state["channels"],
            potential_formula=inputs["potential_formula"],
            current_formula=inputs["current_formula"],
            e_eq=inputs["e_eq"],
            segment_index=inputs["active_segment_index"],
        )

    def set_fitting_lock(self, locked: bool) -> None:
        app = self.app
        app._app_state["_fitting_lock"] = locked
        target_state = "disabled" if locked else "normal"
        app.btn_run.configure(state=target_state)
        app.btn_manual.configure(state=target_state)
        app.btn_export.configure(state=target_state)
        app.combo_file.configure(state=target_state)
        if not locked:
            pending_gen = app._app_state.get("_pending_gen", 0)
            if pending_gen > 0:
                app._app_state["_pending_gen"] = 0
                self.restore_or_autorun()

    def compute_segments(
        self,
        inputs: dict,
        *,
        precomputed_segments: list | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[dict[int, PreparedSeries], dict[int, TafelFit], dict[int, str]]:
        app = self.app
        channels = app._app_state["channels"]
        segments = precomputed_segments if precomputed_segments else build_segment_infos(channels, inputs["potential_formula"])
        prepared_map: dict[int, PreparedSeries] = {}
        fit_map: dict[int, TafelFit] = {}
        error_map: dict[int, str] = {}
        for seg_idx in inputs["processing_segment_indices"]:
            if cancelled and cancelled():
                break
            seg_prepared = prepare_series(
                channels,
                potential_formula=inputs["potential_formula"],
                current_formula=inputs["current_formula"],
                e_eq=inputs["e_eq"],
                segment_index=seg_idx,
                precomputed_segments=segments,
            )
            prepared_map[seg_idx] = seg_prepared
            try:
                fit_map[seg_idx] = auto_tafel_fit(
                    seg_prepared.eta, seg_prepared.j,
                    min_window=inputs["min_window"],
                    max_window=inputs["max_window"],
                    eta_range=inputs["eta_range"],
                    logj_range=inputs["logj_range"],
                    min_r2=inputs["min_r2"],
                    fit_priority=inputs["fit_priority"],
                )
            except Exception as exc:
                error_map[seg_idx] = str(exc)
        return prepared_map, fit_map, error_map

    def cache_current_result(self) -> None:
        app = self.app
        if app._app_state["tdms_path"] is None or app._app_state["prepared"] is None:
            return
        inputs = self.collect_inputs()
        cache_key = c.make_result_cache_key(
            tdms_path=app._app_state["tdms_path"],
            potential_formula=inputs["potential_formula"],
            current_formula=inputs["current_formula"],
            e_eq=inputs["e_eq"],
            active_segment_index=inputs["active_segment_index"],
            selected_segment_indices=tuple(inputs["selected_segment_indices"]),
            min_window=inputs["min_window"],
            max_window=inputs["max_window"],
            eta_range=inputs["eta_range"],
            logj_range=inputs["logj_range"],
            min_r2=inputs["min_r2"],
            fit_priority=inputs["fit_priority"],
        )
        app._app_state["result_cache"][cache_key] = {
            "prepared": app._app_state["prepared"],
            "fit": app._app_state["fit"],
            "prepared_by_segment": dict(app._app_state["prepared_by_segment"]),
            "fit_by_segment": dict(app._app_state["fit_by_segment"]),
            "fit_error_by_segment": dict(app._app_state["fit_error_by_segment"]),
            "selected_segment_indices": list(app._app_state["selected_segment_indices"]),
            "active_segment_index": int(app._app_state["active_segment_index"]),
            "view_state": r.capture_plot_view_state(app, app.fig),
            "limits": r.capture_axes_limits(app),
        }
        app._app_state["result_cache"].move_to_end(cache_key)
        from gui.app import MAX_CACHE_SIZE
        while len(app._app_state["result_cache"]) > MAX_CACHE_SIZE:
            app._app_state["result_cache"].pop(next(iter(app._app_state["result_cache"])))
        app._app_state["current_result_keys"][str(app._app_state["tdms_path"])] = cache_key
        app._save_current_file_ui_state()
        app.files.refresh_file_choices(preferred_path=app._app_state["tdms_path"])

    def restore_or_autorun(self) -> None:
        app = self.app
        if app._app_state["tdms_path"] is None or app._app_state["channels"] is None:
            return
        try:
            app._save_current_file_ui_state()
            inputs = self.collect_inputs()
            # Capture current view state before re-rendering so segment toggle/click
            # preserves the user's zoom/pan; only formula changes and file switches reset.
            current_view = (
                r.capture_plot_view_state(app, app.fig)
                if len(app.fig.axes) >= 2
                else None
            )
            cache_key = c.make_result_cache_key(
                tdms_path=app._app_state["tdms_path"],
                potential_formula=inputs["potential_formula"],
                current_formula=inputs["current_formula"],
                e_eq=inputs["e_eq"],
                active_segment_index=inputs["active_segment_index"],
                selected_segment_indices=tuple(inputs["selected_segment_indices"]),
                min_window=inputs["min_window"],
                max_window=inputs["max_window"],
                eta_range=inputs["eta_range"],
                logj_range=inputs["logj_range"],
                min_r2=inputs["min_r2"],
                fit_priority=inputs["fit_priority"],
            )
            cached = app._app_state["result_cache"].get(cache_key)
            if cached is not None:
                app._app_state["prepared"] = cached["prepared"]
                app._app_state["fit"] = cached["fit"]
                app._app_state["prepared_by_segment"] = dict(
                    cached.get("prepared_by_segment", {app._app_state["prepared"].segment.index: app._app_state["prepared"]})
                )
                app._app_state["fit_by_segment"] = dict(cached.get("fit_by_segment", {}))
                app._app_state["fit_error_by_segment"] = dict(cached.get("fit_error_by_segment", {}))
                app._app_state["manual_mode"] = False
                app._app_state["current_result_keys"][str(app._app_state["tdms_path"])] = cache_key
                app.segments.refresh_buttons()
                r.draw(app, cached["prepared"], cached["fit"],
                       preserve_view_state=current_view or cached.get("view_state") or cached.get("limits"))
                app.status_var.set("已恢复已处理状态 ✓")
                app.files.refresh_file_choices(preferred_path=app._app_state["tdms_path"])
                return
            app._app_state["prepared"] = None
            app._app_state["fit"] = None
            app._app_state["prepared_by_segment"] = {}
            app._app_state["fit_by_segment"] = {}
            app._app_state["fit_error_by_segment"] = {}
            self.run_fit(auto_trigger=True, preserve_view_state=current_view)
        except Exception as exc:
            app.status_var.set(f"自动处理失败：{exc}")

    def apply_formulas_and_fit(self) -> None:
        app = self.app
        if app._app_state["channels"] is None:
            messagebox.showwarning("提示", "请先选择并加载数据文件")
            return
        app._save_current_file_ui_state()
        if not app.files.refresh_segments(show_error=True):
            return
        self.run_fit()

    def run_fit(self, auto_trigger: bool = False, *, preserve_view_state=None) -> None:
        app = self.app
        if app._app_state["channels"] is None:
            messagebox.showwarning("提示", "请先选择并加载数据文件")
            return
        if app._app_state["_fitting_lock"]:
            return
        app._app_state["_op_generation"] += 1
        current_gen = app._app_state["_op_generation"]
        self.set_fitting_lock(True)
        app.status_var.set("正在自动识别并拟合…" if not auto_trigger else "正在自动恢复并拟合…")
        app.update_idletasks()

        def _task():
            try:
                inputs = self.collect_inputs()
                segments = app._app_state.get("segments") or []
                prepared_by_segment, fit_by_segment, fit_error_by_segment = self.compute_segments(
                    inputs,
                    precomputed_segments=segments,
                    cancelled=lambda: app._app_state["_op_generation"] != current_gen,
                )
                active_index = inputs["active_segment_index"]
                prepared = prepared_by_segment[active_index]
                fit = fit_by_segment.get(active_index)
                fit_error = fit_error_by_segment.get(active_index)

                def _finish():
                    if app._app_state["_op_generation"] != current_gen:
                        return
                    app._app_state["prepared_by_segment"].update(prepared_by_segment)
                    app._app_state["fit_by_segment"].update(fit_by_segment)
                    app._app_state["fit_error_by_segment"].update(fit_error_by_segment)
                    live_active = app._app_state["active_segment_index"]
                    if live_active in prepared_by_segment:
                        app._app_state["prepared"] = prepared_by_segment[live_active]
                        app._app_state["fit"] = fit_by_segment.get(live_active)
                    elif active_index in prepared_by_segment:
                        app._app_state["prepared"] = prepared_by_segment[active_index]
                        app._app_state["fit"] = fit_by_segment.get(active_index)
                    app._app_state["manual_mode"] = False
                    live_fit_error = (
                        fit_error_by_segment.get(live_active)
                        or app._app_state["fit_error_by_segment"].get(live_active)
                    )
                    # 拟合完成后 auto-scale：传入空 dict 使 apply_plot_view_state 不操作，
                    # render_figure 的自动坐标适配生效
                    pvs = preserve_view_state if preserve_view_state is not None else {}
                    r.draw(app, app._app_state["prepared"], app._app_state["fit"], fit_error=live_fit_error,
                           preserve_view_state=pvs)
                    app.segments.refresh_buttons()
                    if fit_by_segment:
                        self.cache_current_result()
                        failed_count = len(fit_error_by_segment)
                        prefix = "自动处理完成" if auto_trigger else "自动拟合完成"
                        app.status_var.set(f"{prefix} ✓，成功 {len(fit_by_segment)} 段，失败 {failed_count} 段")
                        log_info(f"{prefix}: 成功 {len(fit_by_segment)} 段, 失败 {failed_count} 段")
                    else:
                        app.status_var.set("所选分段均拟合失败（已显示数据点）")
                        log_error("拟合: 所有分段均失败")

                app.after(0, _finish)
            except Exception as exc:
                tb = traceback.format_exc()
                log_error(f"拟合异常: {exc}\n{tb}")
                app.after(0, lambda: app.status_var.set("拟合失败"))
                app.after(0, lambda: messagebox.showerror("拟合失败", f"错误：{exc}"))
            finally:
                app.after(0, lambda: self.set_fitting_lock(False))

        threading.Thread(target=_task, daemon=True).start()

    def on_manual_select(self, eclick, erelease) -> None:
        app = self.app
        if not app._app_state["manual_mode"] or app._app_state["prepared"] is None:
            return
        coords = (eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata)
        if any(v is None for v in coords):
            return
        try:
            limits = r.capture_axes_limits(app)
            inputs = self.collect_inputs()
            fit = manual_tafel_fit(
                app._app_state["prepared"].eta, app._app_state["prepared"].j,
                x_min=eclick.xdata, x_max=erelease.xdata,
                y_min=eclick.ydata, y_max=erelease.ydata,
                eta_range=inputs["eta_range"], logj_range=inputs["logj_range"],
                min_r2=inputs["min_r2"],
            )
            active_index = int(app._app_state.get("active_segment_index", app._app_state["prepared"].segment.index))
            app._app_state["fit_by_segment"][active_index] = fit
            app._app_state["fit_error_by_segment"].pop(active_index, None)
            app._app_state["fit"] = fit
            app._app_state["manual_mode"] = False
            r.draw(app, app._app_state["prepared"], fit, preserve_view_state=limits)
            self.cache_current_result()
            app.status_var.set("手动拟合完成 ✓")
            log_info(f"手动拟合完成: slope={fit.slope_mv_per_dec:.2f} mV/dec, R²={fit.r2:.4f}")
        except Exception as exc:
            app._app_state["manual_mode"] = False
            r.refresh_selector(app)
            log_error(f"手动拟合失败: {exc}")
            messagebox.showerror("手动拟合失败", str(exc))
            app.status_var.set("手动拟合失败")

    def enable_manual_mode(self) -> None:
        app = self.app
        if app._app_state["channels"] is None:
            messagebox.showwarning("提示", "请先选择并加载数据文件")
            return
        if app._app_state["_fitting_lock"]:
            return
        try:
            r.clear_toolbar_mode(app)
            inputs = self.collect_inputs()
            preserve_view_state = (
                r.capture_plot_view_state(app, app.fig) if len(app.fig.axes) >= 2 else None
            )
            active_index = inputs["active_segment_index"]
            segments = app._app_state.get("segments") or []
            prepared_by_segment, fit_by_segment, fit_error_by_segment = self.compute_segments(
                inputs, precomputed_segments=segments,
            )
            prepared = prepared_by_segment[active_index]
            app._app_state["prepared"] = prepared
            app._app_state["selected_segment_indices"] = list(inputs["selected_segment_indices"])
            app._app_state["active_segment_index"] = active_index
            app._app_state["prepared_by_segment"] = prepared_by_segment
            app._app_state["fit_by_segment"] = fit_by_segment
            app._app_state["fit_error_by_segment"] = fit_error_by_segment
            fit = fit_by_segment.get(active_index)
            fit_error = fit_error_by_segment.get(active_index)
            app._app_state["fit"] = fit
            app._app_state["manual_mode"] = True
            r.draw(app, prepared, fit, preserve_view_state=preserve_view_state, fit_error=fit_error)
            if fit_by_segment:
                self.cache_current_result()
            r.refresh_selector(app)
            app.status_var.set(
                "请在右侧 Tafel 图上框选手动拟合区域" if fit is not None else "自动拟合失败，已进入手动框选模式"
            )
        except Exception as exc:
            messagebox.showerror("进入手动模式失败", str(exc))
