from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QStackedWidget
from PySide6.QtCore import Qt

from gui_qt.theme import BG_WINDOW


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
        # Placeholder: will be built by subsequent tasks

    def _init_controllers(self) -> None:
        pass


class ActivityBar(QWidget):
    """48px vertical icon strip for panel switching."""
    pass
