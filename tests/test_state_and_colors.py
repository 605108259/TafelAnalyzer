from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class ColorUtilsTests(unittest.TestCase):
    def test_hex_color_normalization_accepts_hashless_input(self) -> None:
        from ui.color_utils import is_hex_color, normalize_hex_color

        self.assertTrue(is_hex_color("f0f4f7"))
        self.assertEqual(normalize_hex_color("F0F4F7"), "#f0f4f7")

    def test_hex_color_normalization_falls_back_for_invalid_input(self) -> None:
        from ui.color_utils import is_hex_color, normalize_hex_color

        self.assertFalse(is_hex_color("#12"))
        self.assertEqual(normalize_hex_color("#12", fallback="#000000"), "#000000")


class ComparisonStateTests(unittest.TestCase):
    def test_comparison_rename_keeps_full_editable_label(self) -> None:
        import numpy as np
        from core.types import ComparisonItem, PreparedSeries, SegmentInfo
        from ui.state import AppState

        prepared = PreparedSeries(
            raw_e=np.array([0.0]),
            raw_j=np.array([1.0]),
            e=np.array([0.0]),
            j=np.array([1.0]),
            eta=np.array([0.0]),
            e_label="E",
            j_label="j",
            tafel_y_label="eta",
            potential_channel="E",
            current_channel="j",
            potential_formula="[E]",
            current_formula="[j]",
            e_eq=0.0,
            segment=SegmentInfo(index=0, start=0, end=1),
        )
        item = ComparisonItem(
            item_id="file::0",
            file_path=Path("file.cor"),
            file_name="AU-CV",
            segment_index=0,
            prepared=prepared,
            fit=None,
            label="AU-CV-第1段",
            color="#2563eb",
        )
        state = AppState()
        state.comparison.add(item)

        label = state.comparison.rename("file::0", "Pt-CV-第1段-重测")

        self.assertEqual(label, "Pt-CV-第1段-重测")
        self.assertEqual(state.comparison.item_data()[0]["edit_name"], "Pt-CV-第1段-重测")
        self.assertEqual(state.comparison.item_data()[0]["segment_label"], "")


class InteractionStateTests(unittest.TestCase):
    def test_manual_session_is_bound_to_current_path_and_generation(self) -> None:
        from ui.state import AppState

        state = AppState()
        first = Path("first.cor")
        second = Path("second.cor")
        state.files.set_current_path(first)
        generation = state.operations.bump_generation()

        state.interaction.enable_manual(path=first, generation=generation)

        self.assertTrue(state.interaction.manual_is_current(path=first, generation=generation))
        self.assertFalse(state.interaction.manual_is_current(path=second, generation=generation))
        self.assertFalse(state.interaction.manual_is_current(path=first, generation=generation + 1))

    def test_invalidate_interaction_clears_manual_mode_and_selector(self) -> None:
        from ui.state import AppState

        state = AppState()
        state.raw["selector"] = object()
        state.interaction.enable_manual(path=Path("first.cor"), generation=2)

        state.interaction.invalidate()

        self.assertFalse(state.raw["manual_mode"])
        self.assertIsNone(state.raw["selector"])
        self.assertFalse(state.interaction.manual_is_current(path=Path("first.cor"), generation=2))


class AnalysisStateTests(unittest.TestCase):
    def test_begin_file_load_resets_stale_analysis_state(self) -> None:
        from ui.state import AppState

        state = AppState()
        state.raw["prepared"] = object()
        state.raw["fit"] = object()
        state.raw["fit_by_segment"] = {0: object()}
        state.raw["selected_segment_indices"] = [0]
        state.raw["manual_mode"] = True
        state.raw["selector"] = object()

        state.analysis.begin_file_load(Path("new.cor"))

        self.assertEqual(state.files.current_path, Path("new.cor"))
        self.assertIsNone(state.raw["prepared"])
        self.assertIsNone(state.raw["fit"])
        self.assertEqual(state.raw["fit_by_segment"], {})
        self.assertEqual(state.segments.selected_indices, [])
        self.assertFalse(state.raw["manual_mode"])
        self.assertIsNone(state.raw["selector"])

    def test_apply_loaded_file_sets_segments_colors_and_selection(self) -> None:
        from core.types import SegmentInfo
        from ui.state import AppState

        state = AppState()

        rows = state.analysis.apply_loaded_file(
            channels={"E": [1, 2, 3]},
            segment_infos=[
                SegmentInfo(index=0, start=0, end=2),
                SegmentInfo(index=1, start=2, end=3),
            ],
            segment_colors={0: "#111111", 1: "#222222"},
        )

        self.assertEqual([row["index"] for row in rows], [0, 1])
        self.assertEqual(state.raw["segment_colors"], {0: "#111111", 1: "#222222"})
        self.assertEqual(state.segments.active_index, 0)
        self.assertEqual(state.segments.selected_indices, [0, 1])


if __name__ == "__main__":
    unittest.main()
