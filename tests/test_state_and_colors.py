from __future__ import annotations

import sys
import tempfile
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


class PaletteMappingTests(unittest.TestCase):
    def test_interpolated_palette_downsampling_keeps_first_and_last_colors(self) -> None:
        from ui.controllers.file_ctrl import _map_palette_colors

        source = [f"#{i}{i}{i}{i}{i}{i}" for i in range(8)]

        mapped = _map_palette_colors(source, 4, "interpolate")

        self.assertEqual(len(mapped), 4)
        self.assertEqual(mapped[0], source[0])
        self.assertEqual(mapped[-1], source[-1])


class PaletteSettingsTests(unittest.TestCase):
    def test_save_app_settings_accepts_mixed_string_and_int_color_indices(self) -> None:
        from ui import settings
        from ui.state import DEFAULT_SCHEME_NAME

        class App:
            pass

        app = App()
        app._app_state = {
            "palette_schemes": {
                DEFAULT_SCHEME_NAME: {
                    "0": "#111111",
                    1: "#222222",
                },
            },
            "palette_scheme_slot_counts": {DEFAULT_SCHEME_NAME: 2},
            "active_palette_scheme": DEFAULT_SCHEME_NAME,
            "project_history": [],
        }

        original_path = settings.APP_SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings.APP_SETTINGS_PATH = Path(tmp_dir) / "settings.json"
            try:
                settings.save_app_settings(app)
                payload = settings.APP_SETTINGS_PATH.read_text(encoding="utf-8")
            finally:
                settings.APP_SETTINGS_PATH = original_path

        self.assertIn('"0": "#111111"', payload)
        self.assertIn('"1": "#222222"', payload)

    def test_load_app_settings_scans_history_cache_when_settings_file_is_missing(self) -> None:
        from ui import settings
        from ui.state import AppState

        original_path = settings.APP_SETTINGS_PATH
        original_history_dir = settings.HISTORY_CACHE_DIR
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            history_dir = root / "history_cache"
            history_dir.mkdir()
            (history_dir / "2026-05-13 10-20-30.json").write_text(
                '{"selected_paths": ["D:/data/sample.cor"], "current_path": "D:/data/sample.cor"}',
                encoding="utf-8",
            )
            settings.APP_SETTINGS_PATH = root / "missing-settings.json"
            settings.HISTORY_CACHE_DIR = history_dir
            try:
                state = AppState()
                settings.load_app_settings(type("App", (), {"_app_state": state.raw})())
            finally:
                settings.APP_SETTINGS_PATH = original_path
                settings.HISTORY_CACHE_DIR = original_history_dir

        self.assertEqual(len(state.raw["project_history"]), 1)


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


    def test_comparison_upsert_refreshes_data_and_preserves_row_state(self) -> None:
        import numpy as np
        from core.types import ComparisonItem, PreparedSeries, SegmentInfo
        from ui.state import AppState

        def prepared(value: float) -> PreparedSeries:
            return PreparedSeries(
                raw_e=np.array([value]),
                raw_j=np.array([1.0]),
                e=np.array([value]),
                j=np.array([1.0]),
                eta=np.array([value]),
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

        state = AppState()
        first = ComparisonItem(
            item_id="file::0",
            file_path=Path("file.cor"),
            file_name="old",
            segment_index=0,
            prepared=prepared(1.0),
            fit=None,
            label="custom",
            color="#111111",
            visible=False,
        )
        second = ComparisonItem(
            item_id="file::0",
            file_path=Path("file.cor"),
            file_name="new",
            segment_index=0,
            prepared=prepared(2.0),
            fit=None,
            label="new-default",
            color="#222222",
            visible=True,
        )

        self.assertTrue(state.comparison.upsert(first))
        self.assertFalse(state.comparison.upsert(second))

        item = state.comparison.item_by_id("file::0")
        self.assertIsNotNone(item)
        self.assertEqual(item.file_name, "new")
        self.assertEqual(item.label, "custom")
        self.assertEqual(item.color, "#111111")
        self.assertFalse(item.visible)
        self.assertTrue(np.allclose(item.prepared.e, np.array([2.0])))

    def test_comparison_set_all_visible_updates_every_item(self) -> None:
        from core.types import ComparisonItem
        from ui.state import AppState

        state = AppState()
        state.comparison.add(ComparisonItem(
            item_id="file::0",
            file_path=Path("file.cor"),
            file_name="file",
            segment_index=0,
            prepared=None,
            fit=None,
            label="first",
            color="#111111",
            visible=True,
        ))
        state.comparison.add(ComparisonItem(
            item_id="file::1",
            file_path=Path("file.cor"),
            file_name="file",
            segment_index=1,
            prepared=None,
            fit=None,
            label="second",
            color="#222222",
            visible=False,
        ))

        state.comparison.set_all_visible(True)
        self.assertTrue(all(item.visible for item in state.comparison.items))

        state.comparison.set_all_visible(False)
        self.assertTrue(all(not item.visible for item in state.comparison.items))


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
