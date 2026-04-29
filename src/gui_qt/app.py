from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QStackedWidget, QLabel
from PySide6.QtCore import Qt

from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_FORMULA, PANEL_SEGMENTS, PANEL_PARAMS
from gui_qt.panels.file_panel import FilePanel
from gui_qt.panels.formula_panel import FormulaPanel
from gui_qt.panels.segment_panel import SegmentPanel
from gui_qt.theme import BG_WINDOW, BG_CARD
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
        self.setStyleSheet(f"QMainWindow {{ background: {BG_WINDOW}; }}")

        self._init_app_state()
        self._build_ui()
        self._init_controllers()

    def _init_app_state(self) -> None:
        self._app_state: dict = {
            "selected_paths": [],
            "tdms_path": None,
            "channels": None,
            "segments": [],
            "segment_colors": {},
            "comparison_mode": False,
            "comparison_items": [],
            "_op_generation": 0,
        }

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

        layout.addWidget(self.side_stack)

        # Central area
        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        self.param_bar = ParamToolBar()
        self.chart = ChartArea()
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
        if panel_id == -1:
            # Collapse side panel
            self.side_stack.setFixedWidth(0)
            self.side_stack.hide()
            return
        if self.side_stack.isHidden():
            self.side_stack.show()
            self.side_stack.setFixedWidth(320)
        self.side_stack.setCurrentIndex(panel_id)

    def _init_controllers(self) -> None:
        pass
