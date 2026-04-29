from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import matplotlib

from core.types import PreparedSeries, TafelFit
from core.utils import apply_matplotlib_cjk

from gui.logger import log_info

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit("缺少依赖 customtkinter，请先运行：pip install -r requirements.txt") from exc

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from gui.theme import ACCENT, ACCENT_HOVER, ACTIVE_TEXT_COLOR, BG_LIGHT, TEXT_SECONDARY
from gui import settings, palette as p, rendering as r, comparison as comp
from gui.app_builder import build_left_panel, build_chart_area, build_compare_panel
from gui.controllers import FileManager, FittingController, ExportManager, ComparisonManager, SegmentPanel

MAX_CACHE_SIZE = 50

matplotlib.use("TkAgg")
apply_matplotlib_cjk(matplotlib)


if TkinterDnD is not None:
    class DndCTk(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    DndCTk = ctk.CTk


class TafelAnalyzerApp(DndCTk):
    """Tafel Analyzer 主应用（轻量编排层）。"""

    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        super().__init__()
        self.title("Tafel Analyzer")
        self.geometry("1480x900")
        self.minsize(1220, 760)
        self.configure(fg_color=BG_LIGHT)

        self._init_app_state()
        build_left_panel(self)
        build_chart_area(self)
        build_compare_panel(self)
        self._init_controllers()
        self._wire_callbacks()
        self._finish_startup()
        log_info("Tafel Analyzer 启动完成")

    # ━━ 状态初始化 ━━

    def _init_app_state(self) -> None:
        self._app_state: dict = {
            "selected_paths": [],
            "path_lookup": {},
            "tdms_path": None,
            "channels": None,
            "segments": [],
            "segment_lookup": {},
            "segment_colors": {},
            "palette_schemes": {},
            "palette_scheme_slot_counts": {},
            "active_palette_scheme": "默认方案",
            "saved_parameter_defaults": {
                "e_eq": "0",
                "window_range": "12-15",
                "eta_range": "",
                "logj_range": "",
                "min_r2": "0.95",
                "fit_priority": "斜率更低优先",
            },
            "selected_segment_indices": [],
            "active_segment_index": 0,
            "prepared_by_segment": {},
            "fit_by_segment": {},
            "fit_error_by_segment": {},
            "prepared": None,
            "fit": None,
            "segment_panel_expanded": True,
            "segment_item_buttons": {},
            "manual_mode": False,
            "selector": None,
            "ax_tafel": None,
            "single_plot_view_state": None,
            "compare_plot_view_state": None,
            "single_plot_default_view_state": None,
            "compare_plot_default_view_state": None,
            "file_ui_cache": {},
            "result_cache": OrderedDict(),
            "current_result_keys": {},
            "_op_generation": 0,
            "_fitting_lock": False,
            "_pending_gen": 0,
            "_save_settings_timer": None,
            "comparison_items": [],
            "comparison_mode": False,
            "comparison_item_widgets": {},
            "palette_manager_window": None,
        }

    # ━━ 控制器初始化 ━━

    def _init_controllers(self) -> None:
        self.files = FileManager(self)
        self.fitting = FittingController(self)
        self.export_mgr = ExportManager(self)
        self.comparison = ComparisonManager(self)
        self.segments = SegmentPanel(self)

    # ━━ 回调绑定 ━━

    def _wire_callbacks(self) -> None:
        self.btn_choose_files.configure(command=self.files.choose_files)
        self.btn_remove_file.configure(command=self.files.remove_current_file)
        self.combo_file.configure(command=lambda _: self.files.switch_file())
        self.btn_run.configure(command=self.fitting.run_fit)
        self.btn_manual.configure(command=self.fitting.enable_manual_mode)
        self.btn_export.configure(command=self.export_mgr.export_current)
        self.btn_batch.configure(command=self.export_mgr.run_batch)
        self.btn_apply_formulas.configure(command=self.fitting.apply_formulas_and_fit)
        self.btn_add_compare.configure(command=self.comparison.add_from_current)
        self.btn_add_all_processed.configure(command=self.comparison.add_all_processed)
        self.btn_clear_compare.configure(command=self.comparison.clear_all)
        self.btn_export_compare.configure(command=self.export_mgr.export_comparison)
        self.btn_segment_select_all.configure(command=self.segments.select_all)
        self.btn_segment_clear_all.configure(command=self.segments.clear_all)
        self.btn_toggle_params.configure(command=self._toggle_parameter_section)
        self.btn_tab_single.configure(command=lambda: self._switch_mode("single"))
        self.btn_tab_compare.configure(command=lambda: self._switch_mode("compare"))

        # Palette callbacks
        self.option_palette_scheme.configure(
            command=lambda choice: p.set_active_palette_scheme(self, choice)
        )
        self.option_compare_palette_scheme.configure(
            command=lambda choice: p.set_active_palette_scheme(self, choice)
        )
        self.btn_apply_palette_scheme.configure(
            command=lambda: p.apply_palette_scheme_to_current(self)
        )
        self.btn_apply_compare_palette_scheme.configure(
            command=lambda: p.apply_palette_scheme_to_comparison(self)
        )
        self.btn_manage_palette_schemes.configure(
            command=lambda: p.open_palette_scheme_manager(self)
        )
        self.btn_manage_compare_palette_schemes.configure(
            command=lambda: p.open_palette_scheme_manager(self)
        )

        # Formula entry bindings
        self.entry_potential_formula.bind(
            "<FocusOut>", lambda _: self._save_current_file_ui_state()
        )
        self.entry_potential_formula.bind(
            "<Return>", lambda _: self.fitting.apply_formulas_and_fit()
        )
        self.entry_current_formula.bind(
            "<FocusOut>", lambda _: self._save_current_file_ui_state()
        )
        self.entry_current_formula.bind(
            "<Return>", lambda _: self.fitting.apply_formulas_and_fit()
        )

        # Toolbar home override
        self.toolbar.home = lambda: r.reset_origin_view(self)

    # ━━ 启动收尾 ━━

    def _finish_startup(self) -> None:
        self.protocol("WM_DELETE_WINDOW", self._handle_app_close)
        if DND_FILES is not None:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.files.handle_drop)
        settings.load_app_settings(self)
        self.segments.refresh_buttons()
        self._set_result("等待选择数据文件 …")
        r.draw_placeholder(self)

    # ━━ UI 辅助方法 ━━

    def _set_result(self, text: str) -> None:
        # 单行状态显示（原 result_text 已移除，结果信息改在图表区域显示）
        first_line = text.split("\n")[0]
        self.status_var.set(first_line)

    def _set_compare_result(self, text: str) -> None:
        self.compare_result_text.configure(state="normal")
        self.compare_result_text.delete("1.0", "end")
        self.compare_result_text.insert("1.0", text)
        self.compare_result_text.configure(state="disabled")

    # ━━ UI 状态持久化（读取 widget 值，与应用紧耦合） ━━

    def _save_current_file_ui_state(self) -> None:
        settings.persist_parameter_settings(self)
        file_key = settings.current_file_key(self)
        if file_key is None:
            return
        self._app_state["file_ui_cache"][file_key] = {
            "potential_formula": self.entry_potential_formula.get().strip(),
            "current_formula": self.entry_current_formula.get().strip(),
            "e_eq": self.entry_eeq.get().strip(),
            "window_range": self.entry_window_range.get().strip(),
            "eta_range": self.entry_eta_range.get().strip(),
            "logj_range": self.entry_logj_range.get().strip(),
            "min_r2": self.entry_min_r2.get().strip(),
            "fit_priority": self.combo_fit_priority.get().strip(),
            "export_name": self.entry_export_name.get().strip(),
            "segment_selection": settings.get_segment_selection_text(self),
            "segment_label": (
                self._app_state.get("segments", [{}])[self._app_state.get("active_segment_index", 0)].label
                if self._app_state.get("segments") else ""
            ),
            "segment_colors": p.serialize_segment_colors(
                self, self._app_state.get("segment_colors", {})
            ),
        }

    # ━━ 结果格式化（读取 widget 值，与应用紧耦合） ━━

    def _format_result(
        self,
        prepared: PreparedSeries,
        fit: TafelFit | None,
        *,
        fit_error: str | None = None,
    ) -> str:
        path = self._app_state["tdms_path"]
        window_range = self.entry_window_range.get().strip() or "12-15"
        eta_range = self.entry_eta_range.get().strip() or "未限制"
        logj_range = self.entry_logj_range.get().strip() or "未限制"
        min_r2 = self.entry_min_r2.get().strip() or "0"
        fit_priority = self.combo_fit_priority.get().strip() or "斜率更低优先"
        active_index = int(self._app_state.get("active_segment_index", prepared.segment.index))
        selected_indices = list(self._app_state.get("selected_segment_indices", []))
        display_indices = sorted(set(selected_indices + [active_index]))
        prepared_by_segment = self._app_state.get("prepared_by_segment") or {prepared.segment.index: prepared}
        fit_by_segment = self._app_state.get("fit_by_segment") or ({prepared.segment.index: fit} if fit is not None else {})
        fit_error_by_segment = self._app_state.get("fit_error_by_segment") or {}
        lines = [
            f"文件: {path.name if path else '未加载'}",
            f"当前操作分段: 第{active_index + 1}段",
            f"展示/导出分段: {'、'.join(f'第{idx + 1}段' for idx in selected_indices) if selected_indices else '未选择'}",
            f"电压公式: {prepared.potential_formula}",
            f"电流公式: {prepared.current_formula}",
            f"E_eq: {prepared.e_eq:.6g}",
            f"窗口点数范围: {window_range}",
            f"η 范围: {eta_range}",
            f"log(j) 范围: {logj_range}",
            f"最小 R²: {min_r2}",
            f"自动拟合优先: {fit_priority}",
            "",
            "各段结果:",
        ]
        for index in display_indices:
            seg_prepared = prepared_by_segment.get(index)
            seg_fit = fit_by_segment.get(index)
            seg_error = fit_error_by_segment.get(index)
            if seg_prepared is None:
                lines.append(f"第{index + 1}段: 未准备")
                continue
            if seg_fit is None:
                msg = seg_error or (fit_error if index == prepared.segment.index and fit_error else "未拟合")
                lines.append(f"第{index + 1}段: 拟合失败 | {msg}")
                continue
            lines.append(
                f"第{index + 1}段: {seg_fit.mode} | slope={seg_fit.slope_mv_per_dec:.3f} mV/dec | "
                f"R²={seg_fit.r2:.6f} | 点数={seg_fit.selected_count}/{seg_fit.x_log10_j.size}"
            )
        return "\n".join(lines)

    # ━━ 模式切换 ━━

    def _switch_mode(self, mode: str) -> None:
        if len(self.fig.axes) >= 2:
            if self._app_state.get("comparison_mode"):
                self._app_state["compare_plot_view_state"] = r.capture_plot_view_state(self, self.fig)
            else:
                self._app_state["single_plot_view_state"] = r.capture_plot_view_state(self, self.fig)
        is_compare = mode == "compare"
        self._app_state["comparison_mode"] = is_compare
        if is_compare:
            self.btn_tab_compare.configure(fg_color=ACCENT, text_color=ACTIVE_TEXT_COLOR, hover_color=ACCENT_HOVER)
            self.btn_tab_single.configure(fg_color="transparent", text_color=TEXT_SECONDARY, hover_color="#cbd5e1")
            self.left_shell.grid_remove()
            self.compare_left_shell.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
            comp.render_comparison(self, preserve_view_state=self._app_state.get("compare_plot_view_state"))
        else:
            self.btn_tab_single.configure(fg_color=ACCENT, text_color=ACTIVE_TEXT_COLOR, hover_color=ACCENT_HOVER)
            self.btn_tab_compare.configure(fg_color="transparent", text_color=TEXT_SECONDARY, hover_color="#cbd5e1")
            self.compare_left_shell.grid_remove()
            self.left_shell.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
            if self._app_state["prepared"] is not None:
                r.draw(self, self._app_state["prepared"], self._app_state["fit"],
                       preserve_view_state=self._app_state.get("single_plot_view_state"))
            else:
                r.draw_placeholder(self)

    # ━━ 参数折叠/展开 ━━

    def _toggle_parameter_section(self) -> None:
        expanded = not self._app_state.get("segment_panel_expanded", True)
        self._app_state["segment_panel_expanded"] = expanded
        arrow = "▼" if expanded else "▶"
        self.btn_toggle_params.configure(text=f"⚙️ 参数  {arrow}")
        if expanded:
            self.param_container.grid()
        else:
            self.param_container.grid_remove()

    # ━━ 应用关闭 ━━

    def _handle_app_close(self) -> None:
        log_info("Tafel Analyzer 正在关闭…")
        try:
            self._save_current_file_ui_state()
        finally:
            self.destroy()


if __name__ == "__main__":
    app = TafelAnalyzerApp()
    app.mainloop()
