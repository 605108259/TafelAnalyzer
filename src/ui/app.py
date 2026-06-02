from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QStackedLayout, QLabel, QToolButton, QComboBox
from PySide6.QtCore import Qt

from core.version import APP_VERSION
from ui.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE, PANEL_HISTORY
from ui.theme import BG_WINDOW, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY
from ui.state import AppState, create_initial_state
from ui.view_coordinator import ViewCoordinator


class TafelAnalyzerApp(QMainWindow):
    """Tafel Analyzer 主窗口 (PySide6)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tafel Analyzer")
        self.setMinimumSize(1220, 760)
        self.resize(1480, 900)
        self.setAcceptDrops(True)
        self._install_tooltip_style()
        self.setStyleSheet(f"""
            QMainWindow {{ background: {BG_WINDOW}; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        self._init_app_state()
        self._load_settings()
        self._build_ui()
        self.views = ViewCoordinator(self)
        self._init_controllers()
        self._schedule_update_check()

    @property
    def fig(self):
        """The matplotlib Figure (delegates to chart)."""
        return self.chart.fig

    @property
    def canvas(self):
        """The currently-active FigureCanvas (delegates to chart)."""
        return self.chart.canvas

    def closeEvent(self, event) -> None:
        if hasattr(self, "files") and hasattr(self.files, "_worker"):
            from ui.controllers.worker_utils import stop_worker
            stop_worker(self.files._worker)
        if hasattr(self, "fitting") and hasattr(self.fitting, "_worker"):
            from ui.controllers.worker_utils import stop_worker
            stop_worker(self.fitting._worker)
        if hasattr(self, "chart") and hasattr(self.chart, "close_figure"):
            self.chart.close_figure()
        super().closeEvent(event)

    def _install_tooltip_style(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        app.setStyleSheet(f"""
            QToolTip {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                padding: 4px 8px;
                font-size: 11px;
                border-radius: 4px;
                opacity: 255;
            }}
        """)

    def _init_app_state(self) -> None:
        self._app_state: dict = create_initial_state()
        self._app_state["app_version"] = APP_VERSION
        self.state = AppState(self._app_state)

    def _schedule_update_check(self) -> None:
        try:
            from ui.updater import schedule_update_check
            schedule_update_check(self)
        except Exception:
            pass

    def _load_settings(self) -> None:
        try:
            from ui.settings import load_app_settings
            load_app_settings(self)
        except Exception as exc:
            import logging
            logging.debug(
                "Settings load failed: %s: %s",
                type(exc).__name__, exc,
            )

    def _on_formulas_changed(self, pot_f: str, cur_f: str) -> None:
        path = self._app_state.get("tdms_path")
        if path is None:
            return
        key = str(path)
        cache = self._app_state.setdefault("file_ui_cache", {})
        entry = cache.setdefault(key, {})
        entry["potential_formula"] = pot_f
        entry["current_formula"] = cur_f
        if hasattr(self, "files") and not self._app_state.get("_suppress_toolbar_autosave"):
            self.files.schedule_project_autosave()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.MouseButtonPress and hasattr(self, "toolbar") and hasattr(self, "chart"):
            self.toolbar.clear_nav_mode()
            self.chart.cancel_nav_modes()
            if self._app_state.get("manual_mode"):
                self.fitting.disable_manual_mode()
        return super().eventFilter(obj, event)

    def _on_chart_outside_click(self) -> None:
        if hasattr(self, "toolbar"):
            self.toolbar.clear_nav_mode()
        if hasattr(self, "chart"):
            self.chart.cancel_nav_modes()
        if hasattr(self, "_comp_nav_buttons"):
            self._set_comp_nav_active(None)
        if self._app_state.get("manual_mode"):
            self.fitting.disable_manual_mode()
        if hasattr(self, "views"):
            self.views.reset_active_segment()

    def _on_params_changed(self, params: dict) -> None:
        path = self._app_state.get("tdms_path")
        if path is None:
            return
        key = str(path)
        cache = self._app_state.setdefault("file_ui_cache", {})
        entry = cache.setdefault(key, {})
        for k in ("e_eq", "window_range", "eta_range", "logj_range",
                  "min_r2", "fit_priority"):
            if k in params:
                entry[k] = params[k]
        if hasattr(self, "files") and not self._app_state.get("_suppress_toolbar_autosave"):
            self.files.schedule_project_autosave()

    def _on_save_parameter_defaults(self) -> None:
        from ui.settings import normalize_parameter_settings, save_app_settings

        defaults = normalize_parameter_settings(self.toolbar.get_params())
        self._app_state["saved_parameter_defaults"] = defaults
        save_app_settings(self)
        self.status_bar.setText("已保存默认拟合参数，新文件将默认使用这组参数")

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Activity bar
        self.activity_bar = ActivityBar()
        self.activity_bar.panel_clicked.connect(self._on_panel_clicked)
        layout.addWidget(self.activity_bar)

        # Side panel stack (320px)
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(320)
        self.side_stack.installEventFilter(self)
        self.side_stack.layout().setStackingMode(QStackedLayout.StackingMode.StackAll)

        from ui.panels.file_segment import FileSegmentPanel
        from ui.panels.comparison import ComparisonPanel
        from ui.panels.palette import PaletteSidebar
        from ui.panels.history import HistoryPanel

        self.file_segment_panel = FileSegmentPanel()
        self.side_stack.addWidget(self.file_segment_panel)  # index 0 = PANEL_FILES

        self.comparison_panel = ComparisonPanel()
        self.side_stack.addWidget(self.comparison_panel)    # index 1 = PANEL_COMPARISON

        self.palette_sidebar = PaletteSidebar()
        self.side_stack.addWidget(self.palette_sidebar)     # index 2 = PANEL_PALETTE

        self.history_panel = HistoryPanel()
        self.side_stack.addWidget(self.history_panel)       # index 3 = PANEL_HISTORY

        layout.addWidget(self.side_stack)

        # Right area stack
        self.right_stack = QStackedWidget()

        # Chart workspace
        chart_ws = QWidget()
        chart_layout = QVBoxLayout(chart_ws)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        from ui.central.toolbar import ToolBar
        from ui.central.chart_widget import ChartArea
        from ui.central.summary_table import SummaryTable

        self.toolbar = ToolBar()
        self.chart = ChartArea()

        # Minimal nav bar for comparison mode (zoom/pan/save only)
        from ui.theme import BG_HOVER, TEXT_SECONDARY, BORDER, ICON_BUTTON_STYLE, COMBO_BOX_STYLE
        from ui.icons import line_icon
        self._comp_nav = QWidget()
        self._comp_nav.setFixedHeight(36)
        self._comp_nav.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self._comp_nav.setStyleSheet(f"background: {BG_CARD}; border-bottom: 1px solid {BORDER};")
        self._comp_nav.hide()
        _nav = QHBoxLayout(self._comp_nav)
        _nav.setContentsMargins(8, 0, 8, 0)
        _nav.setSpacing(4)
        _nav.addStretch()
        _lsv_lbl = QLabel("LSV")
        _lsv_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        _nav.addWidget(_lsv_lbl)
        self._comp_lsv_style_combo = QComboBox()
        self._comp_lsv_style_combo.setStyleSheet(COMBO_BOX_STYLE)
        self._comp_lsv_style_combo.addItem("点线", "line_marker")
        self._comp_lsv_style_combo.addItem("折线", "line")
        self._comp_lsv_style_combo.addItem("散点", "scatter")
        self._comp_lsv_style_combo.setFixedWidth(78)
        self._comp_lsv_style_combo.setToolTip("LSV 图显示方式")
        _nav.addWidget(self._comp_lsv_style_combo)

        _tafel_lbl = QLabel("Tafel")
        _tafel_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        _nav.addWidget(_tafel_lbl)
        self._comp_tafel_window_combo = QComboBox()
        self._comp_tafel_window_combo.setStyleSheet(COMBO_BOX_STYLE)
        self._comp_tafel_window_combo.addItem("全部", False)
        self._comp_tafel_window_combo.addItem("拟合附近", True)
        self._comp_tafel_window_combo.setFixedWidth(92)
        self._comp_tafel_window_combo.setToolTip("Tafel 图显示全部点或拟合区间附近点")
        _nav.addWidget(self._comp_tafel_window_combo)

        self._comp_nav_buttons: dict[str, QToolButton] = {}
        self._comp_active_tool: str | None = None
        active_style = (
            ICON_BUTTON_STYLE
            + "QToolButton:checked { background: #2563eb; border-radius: 6px; }"
            + "QToolButton:checked:hover { background: #1d4ed8; }"
        )
        for name, tip, cb in [
            ("home", "复位", self._on_comp_nav_home),
            ("back", "后退", self._on_comp_nav_back),
            ("forward", "前进", self._on_comp_nav_forward),
            ("zoom", "缩放", lambda _checked=False: self._on_comp_nav_tool("zoom")),
            ("pan", "平移", lambda _checked=False: self._on_comp_nav_tool("pan")),
        ]:
            b = QToolButton()
            b.setIcon(line_icon(name, color=TEXT_PRIMARY, size=16))
            tooltip = {
                "home": "复位视图",
                "back": "后退视图",
                "forward": "前进视图",
                "zoom": "缩放",
                "pan": "平移",
            }.get(name) or str(tip or "")
            b.setToolTip(tooltip)
            b.setStatusTip(tooltip)
            b.setAccessibleName(tooltip)
            b.setToolTipDuration(5000)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(name in {"zoom", "pan"})
            b.setStyleSheet(active_style if name in {"zoom", "pan"} else ICON_BUTTON_STYLE)
            b.clicked.connect(cb)
            _nav.addWidget(b)
            self._comp_nav_buttons[name] = b
        _save = QToolButton()
        _save.setIcon(line_icon("save", color=TEXT_PRIMARY, size=16))
        _save.setToolTip("保存图片")
        _save.setStatusTip("保存图片")
        _save.setAccessibleName("保存图片")
        _save.setToolTipDuration(5000)
        _save.setCursor(Qt.CursorShape.PointingHandCursor)
        _save.setStyleSheet(ICON_BUTTON_STYLE)
        _save.clicked.connect(self._save_chart_image)
        _nav.addWidget(_save)

        self.summary_table = SummaryTable()
        self.summary_table.setFixedHeight(140)
        self.summary_table.hide()  # shown only in comparison mode

        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 2px 8px; background: {BG_CARD};"
        )
        self.status_bar.setFixedHeight(24)

        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self._comp_nav)
        chart_layout.addWidget(self.chart, stretch=1)
        chart_layout.addWidget(self.summary_table)
        chart_layout.addWidget(self.status_bar)

        self.right_stack.addWidget(chart_ws)  # index 0

        # Palette workspace
        from ui.central.palette_workspace import PaletteWorkspace
        self.palette_workspace = PaletteWorkspace()
        self.right_stack.addWidget(self.palette_workspace)  # index 1

        # History preview workspace
        from ui.central.history_workspace import HistoryWorkspace
        self.history_workspace = HistoryWorkspace()
        self.right_stack.addWidget(self.history_workspace)  # index 2

        layout.addWidget(self.right_stack, stretch=1)

        # Start on file panel
        self.activity_bar.set_active(PANEL_FILES)
        self.side_stack.setCurrentIndex(PANEL_FILES)
        self.right_stack.setCurrentIndex(0)

    def _set_comp_nav_active(self, name: str | None) -> None:
        self._comp_active_tool = name
        for tool_name, btn in self._comp_nav_buttons.items():
            if tool_name not in {"zoom", "pan"}:
                continue
            btn.blockSignals(True)
            btn.setChecked(tool_name == name)
            btn.blockSignals(False)

    def _sync_comparison_plot_controls(self) -> None:
        lsv_style = self._app_state.get("comparison_lsv_style", "line_marker")
        for index in range(self._comp_lsv_style_combo.count()):
            if self._comp_lsv_style_combo.itemData(index) == lsv_style:
                self._comp_lsv_style_combo.blockSignals(True)
                self._comp_lsv_style_combo.setCurrentIndex(index)
                self._comp_lsv_style_combo.blockSignals(False)
                break
        self._comp_tafel_window_combo.blockSignals(True)
        self._comp_tafel_window_combo.setCurrentIndex(
            1 if self._app_state.get("comparison_tafel_fit_window", False) else 0
        )
        self._comp_tafel_window_combo.blockSignals(False)

    def _on_comp_nav_tool(self, name: str) -> None:
        if self._comp_active_tool == name:
            self.chart.cancel_nav_modes()
            self._set_comp_nav_active(None)
            return
        self.chart.cancel_nav_modes()
        self._set_comp_nav_active(name)
        if name == "zoom":
            self.chart.nav_zoom()
        elif name == "pan":
            self.chart.nav_pan()

    def _on_comp_nav_home(self) -> None:
        self._on_nav_home()

    def _on_comp_nav_back(self) -> None:
        self._on_nav_back()

    def _on_comp_nav_forward(self) -> None:
        self._on_nav_forward()

    def _persist_chart_view_state(self, *, autosave: bool = True) -> None:
        from core.rendering import persist_current_plot_view_state

        persist_current_plot_view_state(self)
        if autosave and hasattr(self, "files"):
            self.files.schedule_project_autosave()

    def _on_chart_interaction_finished(self) -> None:
        self._persist_chart_view_state()

    def _on_nav_home(self) -> None:
        if hasattr(self, "toolbar"):
            self.toolbar.clear_nav_mode()
        if hasattr(self, "_comp_nav_buttons"):
            self._set_comp_nav_active(None)
        self.chart.cancel_nav_modes()
        from core.rendering import reset_origin_view

        reset_origin_view(self)
        self._persist_chart_view_state()

    def _on_nav_back(self) -> None:
        if hasattr(self, "toolbar"):
            self.toolbar.clear_nav_mode()
        if hasattr(self, "_comp_nav_buttons"):
            self._set_comp_nav_active(None)
        self.chart.nav_back()
        self._persist_chart_view_state()

    def _on_nav_forward(self) -> None:
        if hasattr(self, "toolbar"):
            self.toolbar.clear_nav_mode()
        if hasattr(self, "_comp_nav_buttons"):
            self._set_comp_nav_active(None)
        self.chart.nav_forward()
        self._persist_chart_view_state()

    def _on_panel_clicked(self, panel_id: int) -> None:
        self.activity_bar.set_active(panel_id)
        self.views.show_panel(panel_id)

    def dragEnterEvent(self, event) -> None:
        if self._dragged_cache_path(event) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        cache_path = self._dragged_cache_path(event)
        if cache_path is not None and hasattr(self, "files"):
            self.files.import_cache_file(cache_path)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _dragged_cache_path(self, event) -> Path | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".json":
                return path
        return None

    def _save_chart_image(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图表图片", "tafel_chart.png",
            "PNG Image (*.png);;PDF (*.pdf);;SVG (*.svg)",
        )
        if not file_path:
            return
        try:
            self.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
            self.status_bar.setText(f"图片已保存: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _init_controllers(self) -> None:
        from ui.controllers.file_ctrl import FileController
        from ui.controllers.fitting_ctrl import FittingController
        from ui.controllers.comparison_ctrl import ComparisonController
        from ui.controllers.export_ctrl import ExportController

        self.files = FileController(self)
        self.fitting = FittingController(self)
        self.comparison = ComparisonController(self)
        self.export_mgr = ExportController(self)

        # Wire file segment panel
        p = self.file_segment_panel
        p.files_selected.connect(self.files.on_files_loaded)
        p.file_activated.connect(self.files.on_file_selected)
        p.file_removed.connect(self.files.on_file_removed)
        p.file_renamed.connect(self.files.on_file_renamed)
        p.cache_import_requested.connect(self.files.import_cache_dialog)
        p.segment_activated.connect(self.files.on_segment_activated)
        p.segment_toggled.connect(self.files.on_segment_toggled)
        p.segment_color_changed.connect(self.files.on_segment_color)
        p.select_all_clicked.connect(self.files.on_select_all)
        p.clear_all_clicked.connect(self.files.on_clear_all)
        p.add_to_comparison.connect(self.comparison.add_from_current)
        p.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        p.palette_apply_clicked.connect(self.files.on_palette_apply)
        p.palette_manage_clicked.connect(lambda: self._on_panel_clicked(PANEL_PALETTE))
        p.export_current.connect(self.export_mgr.export_current)
        p.export_batch.connect(self.export_mgr.run_batch)

        # Wire toolbar
        self.toolbar.fit_clicked.connect(lambda: self.fitting.run_fit(force=True))
        self.toolbar.parameter_defaults_save_clicked.connect(self._on_save_parameter_defaults)
        self.toolbar.manual_clicked.connect(lambda: (self.chart.cancel_nav_modes(), self.fitting.enable_manual_mode()))
        self.toolbar.save_image_clicked.connect(self._save_chart_image)
        self.toolbar.nav_home_clicked.connect(self._on_nav_home)
        self.toolbar.nav_back_clicked.connect(self._on_nav_back)
        self.toolbar.nav_forward_clicked.connect(self._on_nav_forward)
        self.toolbar.nav_zoom_clicked.connect(self.chart.nav_zoom)
        self.toolbar.nav_pan_clicked.connect(self.chart.nav_pan)
        self.toolbar.nav_cancel_clicked.connect(lambda: (self.chart.cancel_nav_modes(), self.fitting.disable_manual_mode() if self._app_state.get("manual_mode") else None))

        # Wire chart canvas outside-axes clicks
        self.chart.clicked_outside_axes.connect(self._on_chart_outside_click)
        self.chart.interaction_finished.connect(self._on_chart_interaction_finished)

        # Wire comparison panel
        cp = self.comparison_panel
        cp.item_visibility_changed.connect(self.comparison.toggle_visibility)
        cp.item_color_changed.connect(self.comparison.update_color)
        cp.item_renamed.connect(self.comparison.rename)
        cp.select_all_clicked.connect(self.comparison.select_all_visible)
        cp.select_none_clicked.connect(self.comparison.select_none_visible)
        cp.clear_all_clicked.connect(self.comparison.clear_all)
        cp.item_remove_clicked.connect(self.comparison.remove_by_id)
        cp.item_clicked.connect(self.comparison.highlight_item)
        cp.move_up_clicked.connect(self.comparison.move_up)
        cp.move_down_clicked.connect(self.comparison.move_down)
        cp.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        cp.palette_apply_clicked.connect(self.files.on_palette_apply_comparison)
        cp.palette_manage_clicked.connect(lambda: self._on_panel_clicked(PANEL_PALETTE))
        self._comp_lsv_style_combo.currentIndexChanged.connect(
            lambda _idx: self.comparison.set_lsv_style(
                self._comp_lsv_style_combo.currentData() or "line_marker"
            )
        )
        self._comp_tafel_window_combo.currentIndexChanged.connect(
            lambda _idx: self.comparison.set_tafel_fit_window(
                bool(self._comp_tafel_window_combo.currentData())
            )
        )
        self._sync_comparison_plot_controls()
        if self._app_state.get("saved_parameter_defaults"):
            self.toolbar.set_params(self._app_state["saved_parameter_defaults"])

        # Wire palette sidebar
        ps = self.palette_sidebar
        ps.scheme_changed.connect(self.files.on_palette_scheme_selected)
        ps.color_changed.connect(self.files.on_palette_color_changed)
        ps.color_count_changed.connect(self.files.on_palette_count_changed)
        ps.apply_to_current_clicked.connect(self.files.on_palette_apply)
        ps.save_as_new_clicked.connect(self.files.on_palette_save_as_new)
        ps.delete_scheme_clicked.connect(self.files.on_palette_delete)
        ps.color_move_requested.connect(self.files.on_palette_color_move)
        ps.color_add_requested.connect(self.files.on_palette_color_add)
        ps.color_remove_requested.connect(self.files.on_palette_color_remove)
        ps.colors_reverse_requested.connect(self.files.on_palette_colors_reverse)
        ps.colors_gradient_requested.connect(self.files.on_palette_colors_gradient)
        ps.default_reset_requested.connect(self.files.on_palette_default_reset)
        ps.color_selected.connect(self.palette_workspace.set_selected_index)

        hp = self.history_panel
        hp.restore_requested.connect(self.history_workspace.request_restore)
        hp.remove_requested.connect(self.files.on_history_remove)
        hp.clear_requested.connect(self.files.on_history_clear)
        hp.selected_entry_changed.connect(self.history_workspace.set_entry)
        self.history_workspace.restore_requested.connect(self.files.import_cache_file)

        # Wire toolbar formula/param persistence
        self.toolbar.formulas_changed.connect(self._on_formulas_changed)
        self.toolbar.params_changed.connect(self._on_params_changed)

        # Wire palette workspace swatch clicks
        self.palette_workspace.swatch_clicked.connect(
            self.files.on_palette_color_changed
        )
        self.palette_workspace.color_selected.connect(
            self.palette_sidebar.set_selected_index
        )

        # Initial palette controls refresh
        self.views.refresh_palette_controls()
        self.views.refresh_file_list()
        self.views.refresh_history_panel()
