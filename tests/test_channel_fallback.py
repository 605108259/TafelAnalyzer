from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class ChannelFallbackTests(unittest.TestCase):
    def test_resolve_formulas_keeps_file_loadable_when_default_channels_do_not_match(self) -> None:
        from ui.controllers.file_ctrl import _resolve_formulas_for_channels

        channels = {
            "Group/VoltageCustom": np.linspace(0.0, 1.0, 12),
            "Group/CurrentCustom": np.linspace(1.0, 2.0, 12),
        }

        potential, current, warnings = _resolve_formulas_for_channels(channels, "", "")

        self.assertEqual(potential, "")
        self.assertEqual(current, "")
        self.assertTrue(warnings)

    def test_fit_click_builds_segments_after_manual_channel_formulas(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.app import TafelAnalyzerApp
        from ui.controllers import fitting_ctrl

        app = QApplication.instance() or QApplication([])
        window = TafelAnalyzerApp()
        window._app_state["channels"] = {
            "Group/VoltageCustom": np.linspace(0.0, 1.0, 24),
            "Group/CurrentCustom": np.linspace(1.0, 2.0, 24),
        }
        window._app_state["segments"] = []
        window._app_state["selected_segment_indices"] = []
        window.toolbar.set_formulas("[Group/VoltageCustom]", "[Group/CurrentCustom]")
        captured: dict[str, object] = {}

        class SignalStub:
            def connect(self, _callback) -> None:
                pass

        class WorkerStub:
            finished = SignalStub()
            error = SignalStub()

            def __init__(self, *args, **kwargs) -> None:
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.generation = None

            def start(self) -> None:
                captured["started"] = True

        try:
            with patch.object(fitting_ctrl, "FitWorker", WorkerStub):
                window.fitting.run_fit(force=True)
        finally:
            window.close()

        self.assertTrue(captured.get("started"))
        self.assertTrue(window._app_state["segments"])
        self.assertEqual(window._app_state["selected_segment_indices"], [0])


if __name__ == "__main__":
    unittest.main()
