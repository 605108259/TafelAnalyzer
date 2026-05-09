import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ui.state import AppState


def test_reset_current_result_clears_analysis_fields():
    state = AppState()
    state.analysis.apply_loaded_file(
        channels={"V": [1, 2]},
        segment_infos=[],
        segment_colors={0: "#ff0000"},
    )
    state.files.reset_current_result()
    assert state.raw["channels"] is None
    assert state.raw["segments"] == []
    assert state.raw["prepared"] is None
    assert state.raw["fit"] is None
    assert state.raw["prepared_by_segment"] == {}
    assert state.raw["fit_by_segment"] == {}
    assert state.raw["active_segment_index"] == 0


def test_begin_file_load_resets_and_sets_path():
    state = AppState()
    state.analysis.begin_file_load(Path("/tmp/test.tdms"))
    assert state.raw["tdms_path"] == Path("/tmp/test.tdms")
    assert state.raw["channels"] is None
    assert state.raw["segments"] == []
    assert state.raw["prepared_by_segment"] == {}
