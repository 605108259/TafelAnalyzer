from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QStackedWidget, QLabel
from PySide6.QtCore import Qt

from gui_qt.activity_bar import ActivityBar, PANEL_FILES
from gui_qt.panels.file_panel import FilePanel
from gui_qt.panels.formula_panel import FormulaPanel
from gui_qt.panels.segment_panel import SegmentPanel
from gui_qt.panels.comparison_panel import ComparisonPanel
from gui_qt.theme import BG_WINDOW, BG_CARD, TEXT_PRIMARY
from gui_qt.central.param_bar import ParamToolBar
from gui_qt.central.chart_widget import ChartArea
from gui_qt.central.chart_toolbar import ChartToolBar


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
            "prepared": None,
            "fit": None,
            "fit_by_segment": {},
            "prepared_by_segment": {},
            "comparison_mode": False,
            "comparison_items": [],
            "saved_parameter_defaults": {},
            "_op_generation": 0,
        }

    def _load_settings(self) -> None:
        try:
            from gui import settings as s
            s.load_app_settings(self)
        except Exception:
            pass  # CTk widget references don't exist in Qt mode

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

        # Side panel stack
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(320)

        # Add panels
        self.file_panel = FilePanel()
        self.side_stack.addWidget(self.file_panel)  # index 0 -> PANEL_FILES
        self.formula_panel = FormulaPanel()
        self.side_stack.addWidget(self.formula_panel)  # index 1 -> PANEL_FORMULA
        self.segment_panel = SegmentPanel()
        self.side_stack.addWidget(self.segment_panel)  # index 2 -> PANEL_SEGMENTS
        self.comparison_panel = ComparisonPanel()
        self.side_stack.addWidget(self.comparison_panel)  # index 3

        layout.addWidget(self.side_stack)

        # Central area
        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        self.param_bar = ParamToolBar()
        self.chart = ChartArea()
        # Compatibility aliases for old-style gui.comparison rendering
        self.fig = self.chart.fig
        self.canvas = self.chart.canvas
        self.chart_toolbar = ChartToolBar()

        self.status_bar = QLabel("就绪")
        self.status_bar.setFixedHeight(24)
        self.status_bar.setStyleSheet(
            f"color: #64748b; font-size: 10px; padding-left: 8px; background: {BG_CARD};"
        )

        self.central_layout.addWidget(self.param_bar)
        self.central_layout.addWidget(self.chart, stretch=1)
        self.central_layout.addWidget(self.chart_toolbar)
        self.central_layout.addWidget(self.status_bar)

        layout.addWidget(self.central_widget, stretch=1)
        self.activity_bar.set_active(PANEL_FILES)

    def _on_panel_clicked(self, panel_id: int) -> None:
        self.side_stack.show()
        self.side_stack.setFixedWidth(320)
        self.side_stack.setCurrentIndex(panel_id)

    def _switch_mode(self, mode: str) -> None:
        if mode == "single":
            self._app_state["comparison_mode"] = False
            self.side_stack.setCurrentIndex(2)  # segment panel
            if hasattr(self, "summary_table"):
                self.summary_table.hide()
        else:
            self._app_state["comparison_mode"] = True
            self.side_stack.setCurrentIndex(3)  # comparison panel
            if hasattr(self, "summary_table"):
                self.summary_table.show()

    def _init_controllers(self) -> None:
        from gui_qt.controllers.file_ctrl import FileController
        from gui_qt.controllers.fitting_ctrl import FittingController
        from gui_qt.controllers.comparison_ctrl import ComparisonController
        from gui_qt.controllers.export_ctrl import ExportController
        from gui_qt.central.summary_table import SummaryTable

        self.files = FileController(self)
        self.fitting = FittingController(self)
        self.comparison = ComparisonController(self)
        self.export_mgr = ExportController(self)

        # Wire file panel
        self.file_panel.files_loaded.connect(self.files.on_files_loaded)
        self.file_panel.file_selected.connect(self.files.on_file_selected)

        # Wire param bar
        self.param_bar.fit_clicked.connect(self.fitting.run_fit)

        # Wire formula panel
        self.formula_panel.apply_clicked.connect(self.fitting.run_fit)

        # Wire chart toolbar
        self.chart_toolbar.save_image_clicked.connect(self.export_mgr.export_current)

        # Wire comparison panel
        self.comparison_panel.delete_selected_clicked.connect(self.comparison.delete_selected)
        self.comparison_panel.move_up_clicked.connect(self.comparison.move_up)
        self.comparison_panel.move_down_clicked.connect(self.comparison.move_down)
        self.comparison_panel.clear_all_clicked.connect(self.comparison.clear_all)
        self.comparison_panel.add_all_clicked.connect(self.comparison.add_all_processed)
        self.comparison_panel.item_visibility_changed.connect(self.comparison.toggle_visibility)
        self.comparison_panel.item_color_changed.connect(self.comparison.update_color)
        self.comparison_panel.item_renamed.connect(self.comparison.rename)

        # Summary table (hidden in single-file mode)
        self.summary_table = SummaryTable()
        self.summary_table.hide()
        self.central_layout.addWidget(self.summary_table)
