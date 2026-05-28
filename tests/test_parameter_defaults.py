from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication


def _qapp():
    return QApplication.instance() or QApplication([])


class ParameterDefaultsTests(unittest.TestCase):
    def test_save_app_settings_persists_saved_parameter_defaults(self) -> None:
        from ui import settings
        from ui.state import AppState

        state = AppState()
        state.raw["saved_parameter_defaults"] = {
            "e_eq": "0.23",
            "window_range": "8-18",
            "eta_range": "0.05-0.35",
            "logj_range": "",
            "min_r2": "0.98",
            "fit_priority": "R²优先",
        }
        app = type("App", (), {"_app_state": state.raw})()
        original_path = settings.APP_SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings.APP_SETTINGS_PATH = Path(tmp_dir) / "settings.json"
            try:
                settings.save_app_settings(app)
                saved = settings.APP_SETTINGS_PATH.read_text(encoding="utf-8")
            finally:
                settings.APP_SETTINGS_PATH = original_path

        self.assertIn('"saved_parameter_defaults"', saved)
        self.assertIn('"e_eq": "0.23"', saved)

    def test_toolbar_save_button_signal_updates_saved_defaults(self) -> None:
        _qapp()
        from ui.app import TafelAnalyzerApp

        window = TafelAnalyzerApp()
        window.toolbar.set_params({
            "e_eq": "0.23",
            "window_range": "8-18",
            "eta_range": "0.05-0.35",
            "logj_range": "",
            "min_r2": "0.98",
            "fit_priority": "R²优先",
        })

        try:
            window.toolbar.parameter_defaults_save_clicked.emit()
            defaults = window._app_state["saved_parameter_defaults"]
        finally:
            window.close()

        self.assertEqual(defaults["e_eq"], "0.23")
        self.assertEqual(defaults["window_range"], "8-18")
        self.assertEqual(defaults["fit_priority"], "R²优先")

    def test_loaded_file_without_cached_params_uses_saved_defaults(self) -> None:
        _qapp()
        import numpy as np
        from core.types import SegmentInfo
        from ui.app import TafelAnalyzerApp

        window = TafelAnalyzerApp()
        window._app_state["tdms_path"] = Path("D:/data/new_file.cor")
        window._app_state["selected_paths"] = [window._app_state["tdms_path"]]
        window._app_state["saved_parameter_defaults"] = {
            "e_eq": "0.31",
            "window_range": "9-19",
            "eta_range": "0.1-0.4",
            "logj_range": "",
            "min_r2": "0.99",
            "fit_priority": "R²优先",
        }

        try:
            window.files._on_load_finished(
                {"E": np.linspace(0, 1, 12), "I": np.linspace(1, 2, 12)},
                "[E]",
                "[I]",
                [SegmentInfo(index=0, start=0, end=12)],
                [],
                window._app_state["tdms_path"],
                window.state.operations.generation,
            )
            params = window.toolbar.get_params()
        finally:
            window.close()

        self.assertEqual(params["e_eq"], "0.31")
        self.assertEqual(params["window_range"], "9-19")
        self.assertEqual(params["min_r2"], "0.99")


if __name__ == "__main__":
    unittest.main()
