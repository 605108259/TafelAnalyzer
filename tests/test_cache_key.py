import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.cache import make_result_cache_key


def test_cache_key_does_not_include_active_segment_index():
    """active_segment_index is UI state and must not affect cache keys."""
    kwargs = dict(
        tdms_path=Path("/data/test.tdms"),
        potential_formula="[Vgs]",
        current_formula="[Igs]",
        e_eq=0.0,
        selected_segment_indices=(0, 1),
        min_window=5,
        max_window=50,
        eta_range=None,
        logj_range=None,
        min_r2=0.95,
        fit_priority="r2",
    )
    # The function no longer accepts active_segment_index at all.
    key = make_result_cache_key(**kwargs)
    assert isinstance(key, tuple)
    # Verify no integer that looks like a segment index leaks in
    # (selected_segment_indices should still be present as a tuple)
    assert (0, 1) in key
