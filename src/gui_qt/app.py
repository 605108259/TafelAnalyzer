from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel

from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE
from gui_qt.theme import BG_WINDOW, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY
from core.types import COMPARISON_COLORS


class TafelAnalyzerApp(QMainWindow):
    """Tafel Analyzer 主窗口 (PySide6)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tafel Analyzer")
        self.setMinimumSize(1220, 760)
        self.resize(1480, 900)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {BG_WINDOW}; }}
            QToolTip {{
                background: {TEXT_PRIMARY};
                color: {BG_CARD};
                border: none;
                padding: 4px 8px;
                font-size: 11px;
                border-radius: 4px;
            }}
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
        self._init_controllers()

    def _init_app_state(self) -> None:
        self._app_state: dict = {
            "selected_paths": [],
            "tdms_path": None,
            "channels": None,
            "segments": [],
            "segment_colors": {},
            "active_segment_index": 0,
            "selected_segment_indices": [],
            "prepared": None,
            "fit": None,
            "fit_by_segment": {},
            "prepared_by_segment": {},
            "fit_error_by_segment": {},
            "manual_mode": False,
            "selector": None,
            "comparison_mode": False,
            "comparison_items": [],
            "palette_schemes": {"默认方案": {str(i): c for i, c in enumerate([
                "#b90746", "#0891b2", "#7c3aed", "#16a34a", "#f59e0b",
                "#dc2626", "#2563eb", "#d946ef", "#0ea5e9", "#84cc16",
            ])}},
            "palette_scheme_slot_counts": {"默认方案": 10},
            "active_palette_scheme": "默认方案",
            "saved_parameter_defaults": {},
            "file_ui_cache": {},
            "result_cache": {},
            "current_result_keys": {},
            "_op_generation": 0,
            "_fitting_lock": False,
        }

    def _load_settings(self) -> None:
        try:
            from gui import settings as s
            s.load_app_settings(self)
        except (ImportError, AttributeError, KeyError) as exc:
            # Expected in Qt mode — CTk widget attrs don't exist
            import logging
            logging.debug(
                "Settings load skipped (Qt mode): %s: %s",
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
        if self._app_state.get("manual_mode"):
            self.fitting.disable_manual_mode()

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

        from gui_qt.panels.file_segment import FileSegmentPanel
        from gui_qt.panels.comparison import ComparisonPanel
        from gui_qt.panels.palette import PaletteSidebar

        self.file_segment_panel = FileSegmentPanel()
        self.side_stack.addWidget(self.file_segment_panel)  # index 0 = PANEL_FILES

        self.comparison_panel = ComparisonPanel()
        self.side_stack.addWidget(self.comparison_panel)    # index 1 = PANEL_COMPARISON

        self.palette_sidebar = PaletteSidebar()
        self.side_stack.addWidget(self.palette_sidebar)     # index 2 = PANEL_PALETTE

        layout.addWidget(self.side_stack)

        # Right area stack
        self.right_stack = QStackedWidget()

        # Chart workspace
        chart_ws = QWidget()
        chart_layout = QVBoxLayout(chart_ws)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        from gui_qt.central.toolbar import ToolBar
        from gui_qt.central.chart_widget import ChartArea
        from gui_qt.central.summary_table import SummaryTable

        self.toolbar = ToolBar()
        self.chart = ChartArea()
        # Compatibility aliases for old-style gui.comparison rendering
        self.fig = self.chart.fig
        self.canvas = self.chart.canvas

        self.summary_table = SummaryTable()
        self.summary_table.setFixedHeight(140)
        self.summary_table.hide()  # shown only in comparison mode

        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 2px 8px; background: {BG_CARD};"
        )
        self.status_bar.setFixedHeight(24)

        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self.chart, stretch=1)
        chart_layout.addWidget(self.summary_table)
        chart_layout.addWidget(self.status_bar)

        self.right_stack.addWidget(chart_ws)  # index 0

        # Palette workspace
        from gui_qt.central.palette_workspace import PaletteWorkspace
        self.palette_workspace = PaletteWorkspace()
        self.right_stack.addWidget(self.palette_workspace)  # index 1

        layout.addWidget(self.right_stack, stretch=1)

        # Start on file panel
        self.activity_bar.set_active(PANEL_FILES)
        self.side_stack.setCurrentIndex(PANEL_FILES)
        self.right_stack.setCurrentIndex(0)

    def _on_panel_clicked(self, panel_id: int) -> None:
        if panel_id < 0:
            self.side_stack.hide()
            return
        self.side_stack.show()
        self.side_stack.setCurrentIndex(panel_id)

        if panel_id == PANEL_FILES:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = False
            self.summary_table.hide()
        elif panel_id == PANEL_COMPARISON:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = True
            self.summary_table.show()
        elif panel_id == PANEL_PALETTE:
            self.right_stack.setCurrentIndex(1)  # palette workspace
            self.summary_table.hide()
            self._update_palette_workspace()

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

    def _update_palette_workspace(self):
        scheme_name = self._app_state.get("active_palette_scheme", "默认方案")
        schemes = self._app_state.get("palette_schemes", {})
        slot_count = self._app_state.get("palette_scheme_slot_counts", {}).get(scheme_name, 8)
        colors = []
        names = []
        scheme_colors = schemes.get(scheme_name, {})
        for i in range(slot_count):
            colors.append(scheme_colors.get(str(i), COMPARISON_COLORS[i % len(COMPARISON_COLORS)]))
            names.append(f"第{i+1}段")
        self.palette_workspace.set_scheme(scheme_name, colors, names)

    def _switch_mode(self, mode: str) -> None:
        if mode == "single":
            self._app_state["comparison_mode"] = False
            self.activity_bar.set_active(PANEL_FILES)
            self.side_stack.setCurrentIndex(PANEL_FILES)
            self.right_stack.setCurrentIndex(0)
            self.summary_table.hide()
        else:
            self._app_state["comparison_mode"] = True
            self.activity_bar.set_active(PANEL_COMPARISON)
            self.side_stack.setCurrentIndex(PANEL_COMPARISON)
            self.right_stack.setCurrentIndex(0)
            self.summary_table.show()

    def _init_controllers(self) -> None:
        from gui_qt.controllers.file_ctrl import FileController
        from gui_qt.controllers.fitting_ctrl import FittingController
        from gui_qt.controllers.comparison_ctrl import ComparisonController
        from gui_qt.controllers.export_ctrl import ExportController

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
        self.toolbar.fit_clicked.connect(self.fitting.run_fit)
        self.toolbar.manual_clicked.connect(lambda: (self.chart.cancel_nav_modes(), self.fitting.enable_manual_mode()))
        self.toolbar.save_image_clicked.connect(self._save_chart_image)
        self.toolbar.nav_home_clicked.connect(self.chart.nav_home)
        self.toolbar.nav_back_clicked.connect(self.chart.nav_back)
        self.toolbar.nav_forward_clicked.connect(self.chart.nav_forward)
        self.toolbar.nav_zoom_clicked.connect(self.chart.nav_zoom)
        self.toolbar.nav_pan_clicked.connect(self.chart.nav_pan)
        self.toolbar.nav_cancel_clicked.connect(lambda: (self.chart.cancel_nav_modes(), self.fitting.disable_manual_mode() if self._app_state.get("manual_mode") else None))

        # Wire chart canvas outside-axes clicks
        self.chart.clicked_outside_axes.connect(self._on_chart_outside_click)

        # Wire comparison panel
        cp = self.comparison_panel
        cp.item_visibility_changed.connect(self.comparison.toggle_visibility)
        cp.item_color_changed.connect(self.comparison.update_color)
        cp.item_renamed.connect(self.comparison.rename)
        cp.add_all_clicked.connect(self.comparison.add_all_processed)
        cp.clear_all_clicked.connect(self.comparison.clear_all)
        cp.delete_selected_clicked.connect(self.comparison.delete_selected)
        cp.move_up_clicked.connect(self.comparison.move_up)
        cp.move_down_clicked.connect(self.comparison.move_down)
        cp.export_clicked.connect(self.export_mgr.export_comparison)
        cp.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        cp.palette_apply_clicked.connect(self.files.on_palette_apply_comparison)
        cp.palette_manage_clicked.connect(lambda: self._on_panel_clicked(PANEL_PALETTE))

        # Wire palette sidebar
        ps = self.palette_sidebar
        ps.scheme_changed.connect(self.files.on_palette_scheme_selected)
        ps.color_changed.connect(self.files.on_palette_color_changed)
        ps.color_count_changed.connect(self.files.on_palette_count_changed)
        ps.apply_to_current_clicked.connect(self.files.on_palette_apply)
        ps.save_as_new_clicked.connect(self.files.on_palette_save_as_new)
        ps.delete_scheme_clicked.connect(self.files.on_palette_delete)

        # Wire toolbar formula/param persistence
        self.toolbar.formulas_changed.connect(self._on_formulas_changed)
        self.toolbar.params_changed.connect(self._on_params_changed)

        # Wire palette workspace swatch clicks
        self.palette_workspace.swatch_clicked.connect(
            self.files.on_palette_color_changed
        )

        # Initial palette controls refresh
        self.files._refresh_palette_controls()
