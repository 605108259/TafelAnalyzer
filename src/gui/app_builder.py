from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit("缺少依赖 customtkinter，请先运行：pip install -r requirements.txt") from exc
import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_LIGHT,
    BORDER_COLOR,
    CARD_BG,
    COMBO_BUTTON_COLOR,
    COMBO_BUTTON_HOVER,
    COMBO_DROPDOWN_BG,
    COMBO_DROPDOWN_HOVER,
    CYAN,
    CYAN_HOVER,
    ENTRY_BG,
    MPL_RC,
    PURPLE,
    PURPLE_HOVER,
    SUCCESS,
    SUCCESS_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    WARNING_HOVER,
)
from gui.tooltip import ToolTip
from gui.widgets import make_combo_row, make_entry_row, make_section_label

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


def build_left_panel(app: TafelAnalyzerApp) -> None:
    """Left panel: file selection, formulas, operations, segments, collapsible parameters."""
    app.left_shell = ctk.CTkFrame(
        app, width=430, fg_color=CARD_BG, corner_radius=14,
        border_width=1, border_color=BORDER_COLOR,
    )
    app.left_shell.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
    app.left_shell.grid_rowconfigure(0, weight=1)
    app.left_shell.grid_columnconfigure(0, weight=1)
    app.left = ctk.CTkScrollableFrame(app.left_shell, fg_color="transparent", corner_radius=0)
    app.left.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
    app.left.grid_columnconfigure(1, weight=1)

    # ━━ 文件 ━━
    make_section_label(app.left, "📂 文件", row=0)

    app.btn_choose_files = ctk.CTkButton(
        app.left, text="选择数据文件…",
        fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8, height=36,
    )
    app.btn_choose_files.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(6, 6))

    app.file_info_var = ctk.StringVar(value="未选择文件")
    ctk.CTkLabel(
        app.left, textvariable=app.file_info_var,
        text_color=TEXT_SECONDARY, font=ctk.CTkFont(size=11), anchor="w",
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 2))

    # File row: combo + remove button inline
    app.file_row_frame = ctk.CTkFrame(app.left, fg_color="transparent")
    app.file_row_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
    app.file_row_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(app.file_row_frame, text="当前处理文件:", text_color=TEXT_SECONDARY, anchor="e").grid(
        row=0, column=0, sticky="e", padx=(10, 4), pady=4,
    )
    app.combo_file = ctk.CTkComboBox(
        app.file_row_frame, values=[""], width=220,
        border_color=BORDER_COLOR, fg_color=ENTRY_BG,
        button_color=COMBO_BUTTON_COLOR, button_hover_color=COMBO_BUTTON_HOVER,
        dropdown_fg_color=COMBO_DROPDOWN_BG, dropdown_hover_color=COMBO_DROPDOWN_HOVER,
        dropdown_text_color=TEXT_PRIMARY, text_color=TEXT_PRIMARY,
    )
    app.combo_file.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=4)
    app.combo_file.set("")
    app.btn_remove_file = ctk.CTkButton(
        app.file_row_frame, text="✕", width=36, height=26,
        fg_color="#fee2e2", hover_color="#fecaca",
        text_color="#dc2626", corner_radius=6,
    )
    app.btn_remove_file.grid(row=0, column=2, sticky="w", padx=(0, 10), pady=4)
    app.entry_export_name = make_entry_row(app.left, "导出名:", row=4, placeholder="默认使用文件名")

    # ━━ 公式 ━━
    make_section_label(app.left, "🧮 公式", row=5)

    app.entry_potential_formula = make_entry_row(
        app.left, "电压公式:", row=6, placeholder="例如 -[Vgs]+0.23",
    )
    app.entry_current_formula = make_entry_row(
        app.left, "电流公式:", row=7, placeholder="例如 [Igs/area]/(2.4e-7+3)",
    )
    app.btn_apply_formulas = ctk.CTkButton(
        app.left, text="应用公式",
        fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8, height=30,
    )
    app.btn_apply_formulas.grid(row=8, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4))

    app.channel_info_var = ctk.StringVar(value="")
    ctk.CTkLabel(
        app.left, textvariable=app.channel_info_var,
        text_color=TEXT_SECONDARY, font=ctk.CTkFont(size=10),
        anchor="w", justify="left", wraplength=390,
    ).grid(row=9, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 2))

    # ━━ 操作 ━━
    make_section_label(app.left, "🚀 操作", row=10)

    app.op_btn_bar = ctk.CTkFrame(app.left, fg_color="transparent")
    app.op_btn_bar.grid(row=11, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 4))
    for i in range(4):
        app.op_btn_bar.grid_columnconfigure(i, weight=1)

    _op_btn_font = ctk.CTkFont(size=18)
    app.btn_run = ctk.CTkButton(
        app.op_btn_bar, text="▶", width=70, height=34,
        fg_color=SUCCESS, hover_color=SUCCESS_HOVER, corner_radius=8, font=_op_btn_font,
    )
    app.btn_run.grid(row=0, column=0, padx=(0, 3))
    ToolTip(app.btn_run, "自动识别并拟合")

    app.btn_manual = ctk.CTkButton(
        app.op_btn_bar, text="🖱", width=70, height=34,
        fg_color=WARNING, hover_color=WARNING_HOVER, corner_radius=8, font=_op_btn_font,
    )
    app.btn_manual.grid(row=0, column=1, padx=3)
    ToolTip(app.btn_manual, "手动框选拟合")

    app.btn_export = ctk.CTkButton(
        app.op_btn_bar, text="💾", width=70, height=34,
        fg_color=PURPLE, hover_color=PURPLE_HOVER, corner_radius=8, font=_op_btn_font,
    )
    app.btn_export.grid(row=0, column=2, padx=3)
    ToolTip(app.btn_export, "导出当前结果")

    app.btn_batch = ctk.CTkButton(
        app.op_btn_bar, text="📦", width=70, height=34,
        fg_color=CYAN, hover_color=CYAN_HOVER, corner_radius=8, font=_op_btn_font,
    )
    app.btn_batch.grid(row=0, column=3, padx=(3, 0))
    ToolTip(app.btn_batch, "批量导出已处理文件")

    # ━━ 分段管理 ━━
    make_section_label(app.left, "📋 分段管理", row=12)

    # Button bar (fixed above segment list)
    app.segment_btn_bar = ctk.CTkFrame(app.left, fg_color="transparent")
    app.segment_btn_bar.grid(row=13, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 2))
    for i in range(3):
        app.segment_btn_bar.grid_columnconfigure(i, weight=1)

    app.btn_segment_select_all = ctk.CTkButton(
        app.segment_btn_bar, text="全选", height=28,
        fg_color="#e2e8f0", hover_color="#cbd5e1",
        text_color=TEXT_PRIMARY, corner_radius=8,
    )
    app.btn_segment_select_all.grid(row=0, column=0, sticky="ew", padx=(0, 3))
    app.btn_segment_clear_all = ctk.CTkButton(
        app.segment_btn_bar, text="全不选", height=28,
        fg_color="#e2e8f0", hover_color="#cbd5e1",
        text_color=TEXT_PRIMARY, corner_radius=8,
    )
    app.btn_segment_clear_all.grid(row=0, column=1, sticky="ew", padx=(3, 3))
    app.btn_add_compare = ctk.CTkButton(
        app.segment_btn_bar, text="📌 加入对比", height=28,
        fg_color="#334155", hover_color="#1e293b",
        text_color="#ffffff", corner_radius=8,
    )
    app.btn_add_compare.grid(row=0, column=2, sticky="ew", padx=(3, 0))

    # Palette row
    app.palette_scheme_var = ctk.StringVar(value="默认方案")
    app.option_palette_scheme = ctk.CTkOptionMenu(
        app.segment_btn_bar, variable=app.palette_scheme_var, values=["默认方案"],
        fg_color="#ffffff", button_color="#e2e8f0", button_hover_color="#cbd5e1",
        dropdown_fg_color="#ffffff", dropdown_hover_color="#eff6ff",
        dropdown_text_color=TEXT_PRIMARY, text_color=TEXT_PRIMARY, height=28,
    )
    app.option_palette_scheme.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
    app.btn_apply_palette_scheme = ctk.CTkButton(
        app.segment_btn_bar, text="应用", height=28,
        fg_color=CYAN, hover_color=CYAN_HOVER,
        text_color="#ffffff", corner_radius=8,
    )
    app.btn_apply_palette_scheme.grid(row=1, column=1, sticky="ew", padx=(3, 3), pady=(6, 0))
    app.btn_manage_palette_schemes = ctk.CTkButton(
        app.segment_btn_bar, text="⚙", width=36, height=28,
        fg_color=PURPLE, hover_color=PURPLE_HOVER,
        text_color="#ffffff", corner_radius=8, font=ctk.CTkFont(size=16),
    )
    app.btn_manage_palette_schemes.grid(row=1, column=2, sticky="w", padx=(3, 0), pady=(6, 0))
    ToolTip(app.btn_manage_palette_schemes, "配色方案管理")

    # Scrollable segment list
    app.segment_scroll = ctk.CTkScrollableFrame(
        app.left, fg_color="#f8fafc", corner_radius=10,
        border_width=1, border_color=BORDER_COLOR, height=120,
    )
    app.segment_scroll.grid(row=14, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4))
    app.segment_scroll.grid_columnconfigure(0, weight=1)
    # CTkScrollableFrame uses bind_all for mousewheel, so both segment_scroll
    # and its parent (app.left) respond to every scroll event globally.  Intercept
    # at toplevel (fires before "all" tag) and when the pointer is inside the inner
    # frame, scroll only the inner one and block the outer.
    def _on_seg_mousewheel(event, seg=app.segment_scroll):
        w = event.widget
        while w is not None:
            if w is seg._parent_canvas or w is seg._parent_frame or w is seg:
                seg._parent_canvas.yview("scroll", -int(event.delta / 6), "units")
                return "break"
            try:
                w = w.master
            except Exception:
                break

    app.bind("<MouseWheel>", _on_seg_mousewheel, add="+")

    # ━━ 参数 (可折叠) ━━
    app.btn_toggle_params = ctk.CTkButton(
        app.left, text="⚙️ 参数  ▼",
        fg_color="transparent", hover_color="#eef2ff",
        text_color=ACCENT, anchor="w",
        font=ctk.CTkFont(size=13, weight="bold"),
        corner_radius=6, height=28,
    )
    app.btn_toggle_params.grid(row=15, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 2))

    app.param_container = ctk.CTkFrame(app.left, fg_color="transparent")
    app.param_container.grid(row=16, column=0, columnspan=2, sticky="ew")
    app.param_container.grid_columnconfigure(1, weight=1)

    app.entry_eeq = make_entry_row(app.param_container, "平衡电位 E_eq:", row=0, default="0")
    app.entry_window_range = make_entry_row(app.param_container, "窗口点数范围:", row=1, default="12-15", placeholder="例如 12-15")
    app.entry_eta_range = make_entry_row(app.param_container, "η 范围:", row=2, placeholder="例如 0-0.5")
    app.entry_logj_range = make_entry_row(app.param_container, "log(j) 范围:", row=3, placeholder="例如 -9--3")
    app.entry_min_r2 = make_entry_row(app.param_container, "最小 R²:", row=4, default="0.95", placeholder="例如 0.95")
    app.combo_fit_priority = make_combo_row(app.param_container, "自动拟合优先:", row=5, values=["斜率更低优先", "R²优先"])

    app.status_var = ctk.StringVar(value="就绪")
    ctk.CTkLabel(
        app.left, textvariable=app.status_var,
        text_color=TEXT_SECONDARY, font=ctk.CTkFont(size=10), anchor="w",
    ).grid(row=22, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))


def build_chart_area(app: TafelAnalyzerApp) -> None:
    """Right panel: figure, canvas, toolbar."""
    app.right = ctk.CTkFrame(
        app, fg_color=CARD_BG, corner_radius=14,
        border_width=1, border_color=BORDER_COLOR,
    )
    app.right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
    app.right.grid_rowconfigure(1, weight=1)
    app.right.grid_columnconfigure(0, weight=1)

    app.grid_columnconfigure(0, weight=0, minsize=430)
    app.grid_columnconfigure(1, weight=1)
    app.grid_rowconfigure(0, weight=1)

    # Tab bar
    app.chart_header = ctk.CTkFrame(app.right, fg_color="transparent", height=40)
    app.chart_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

    app.tab_frame = ctk.CTkFrame(app.chart_header, fg_color="#e2e8f0", corner_radius=10, height=36)
    app.tab_frame.pack(side="left", fill="x", expand=True)
    app.btn_tab_single = ctk.CTkButton(
        app.tab_frame, text="📈  单文件分析",
        fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#ffffff",
        corner_radius=8, height=32, font=ctk.CTkFont(size=13, weight="bold"),
    )
    app.btn_tab_single.pack(side="left", padx=(3, 2), pady=3, fill="x", expand=True)
    app.compare_count_var = ctk.StringVar(value="📊  跨文件对比")
    app.btn_tab_compare = ctk.CTkButton(
        app.tab_frame, textvariable=app.compare_count_var,
        fg_color="transparent", hover_color="#cbd5e1",
        text_color=TEXT_SECONDARY, corner_radius=8, height=32,
        font=ctk.CTkFont(size=13, weight="bold"),
    )
    app.btn_tab_compare.pack(side="left", padx=(2, 3), pady=3, fill="x", expand=True)

    # Figure
    with matplotlib.rc_context(MPL_RC):
        app.fig = Figure(figsize=(10.8, 6.6), dpi=100)
        app.fig.set_facecolor(CARD_BG)

    # Canvas
    app.canvas_frame = ctk.CTkFrame(app.right, fg_color="transparent")
    app.canvas_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 4))
    app.canvas_frame.grid_rowconfigure(0, weight=1)
    app.canvas_frame.grid_columnconfigure(0, weight=1)

    app.canvas = FigureCanvasTkAgg(app.fig, master=app.canvas_frame)
    app.canvas_widget = app.canvas.get_tk_widget()
    app.canvas_widget.configure(bg=CARD_BG, highlightthickness=0)
    app.canvas_widget.grid(row=0, column=0, sticky="nsew")

    # Toolbar
    app.toolbar_frame = ctk.CTkFrame(
        app.right, fg_color="#f8fafc", corner_radius=10,
        border_width=1, border_color=BORDER_COLOR,
    )
    app.toolbar_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
    app.toolbar = NavigationToolbar2Tk(app.canvas, app.toolbar_frame)
    app.toolbar.update()
    app._toolbar_home_original = app.toolbar.home


def build_compare_panel(app: TafelAnalyzerApp) -> None:
    """Comparison mode left panel."""
    app.compare_left_shell = ctk.CTkFrame(
        app, width=430, fg_color=CARD_BG, corner_radius=14,
        border_width=1, border_color=BORDER_COLOR,
    )
    app.compare_left = ctk.CTkScrollableFrame(app.compare_left_shell, fg_color="transparent", corner_radius=0)
    app.compare_left.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
    app.compare_left_shell.grid_rowconfigure(0, weight=1)
    app.compare_left_shell.grid_columnconfigure(0, weight=1)
    app.compare_left.grid_columnconfigure(0, weight=1)

    make_section_label(app.compare_left, "📊 对比项目", row=0)
    app.compare_list_frame = ctk.CTkFrame(app.compare_left, fg_color="transparent")
    app.compare_list_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))
    app.compare_list_frame.grid_columnconfigure(0, weight=1)
    app.compare_left.grid_rowconfigure(1, weight=1)

    app.compare_empty_label = ctk.CTkLabel(
        app.compare_list_frame,
        text="还没有对比项\n\n在单文件分析模式中\n点击 「📌 添加到对比」\n来添加当前段的结果",
        text_color=TEXT_SECONDARY, font=ctk.CTkFont(size=12), justify="center",
    )
    app.compare_empty_label.grid(row=0, column=0, pady=40)

    make_section_label(app.compare_left, "🚀 操作", row=2)
    app.btn_add_all_processed = ctk.CTkButton(
        app.compare_left, text="📥 添加所有已处理段",
        fg_color=CYAN, hover_color=CYAN_HOVER, corner_radius=8, height=34,
    )
    app.btn_add_all_processed.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 4))
    app.btn_clear_compare = ctk.CTkButton(
        app.compare_left, text="🗑 清空对比列表",
        fg_color="#e2e8f0", hover_color="#cbd5e1",
        text_color=TEXT_PRIMARY, corner_radius=8, height=34,
    )
    app.btn_clear_compare.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 4))
    app.btn_export_compare = ctk.CTkButton(
        app.compare_left, text="💾 导出对比图",
        fg_color=PURPLE, hover_color=PURPLE_HOVER, corner_radius=8, height=34,
    )
    app.btn_export_compare.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 4))

    make_section_label(app.compare_left, "🎨 配色方案", row=6)
    app.compare_palette_var = ctk.StringVar(value="默认方案")
    app.option_compare_palette_scheme = ctk.CTkOptionMenu(
        app.compare_left, variable=app.compare_palette_var, values=["默认方案"],
        fg_color="#ffffff", button_color="#e2e8f0", button_hover_color="#cbd5e1",
        dropdown_fg_color="#ffffff", dropdown_hover_color="#eff6ff",
        dropdown_text_color=TEXT_PRIMARY, text_color=TEXT_PRIMARY, height=34,
    )
    app.option_compare_palette_scheme.grid(row=7, column=0, sticky="ew", padx=10, pady=(4, 4))
    app.btn_apply_compare_palette_scheme = ctk.CTkButton(
        app.compare_left, text="应用配色",
        fg_color=CYAN, hover_color=CYAN_HOVER, corner_radius=8, height=34,
    )
    app.btn_apply_compare_palette_scheme.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 4))
    app.btn_manage_compare_palette_schemes = ctk.CTkButton(
        app.compare_left, text="配色方案管理",
        fg_color=PURPLE, hover_color=PURPLE_HOVER, corner_radius=8, height=34,
    )
    app.btn_manage_compare_palette_schemes.grid(row=9, column=0, sticky="ew", padx=10, pady=(0, 4))

    make_section_label(app.compare_left, "📊 汇总", row=10)
    app.compare_result_frame = ctk.CTkFrame(
        app.compare_left, fg_color="#f8fafc", corner_radius=10,
        border_width=1, border_color=BORDER_COLOR,
    )
    app.compare_result_frame.grid(row=11, column=0, sticky="nsew", padx=10, pady=(2, 8))
    app.compare_result_frame.grid_rowconfigure(0, weight=1)
    app.compare_result_frame.grid_columnconfigure(0, weight=1)
    app.compare_result_text = ctk.CTkTextbox(
        app.compare_result_frame, fg_color="transparent", text_color=TEXT_PRIMARY,
        font=ctk.CTkFont(family="Consolas", size=12), wrap="word",
        activate_scrollbars=True, height=180,
    )
    app.compare_result_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
