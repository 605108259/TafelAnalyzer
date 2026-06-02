import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.types import ComparisonItem, PreparedSeries, SegmentInfo
from core.comparison import lsv_plot_kwargs, normalize_lsv_style, tafel_window_mask


def _make_item():
    seg = SegmentInfo(index=0, start=0, end=10)
    ps = PreparedSeries(
        raw_e=np.zeros(10), raw_j=np.zeros(10), e=np.zeros(10), j=np.zeros(10),
        eta=np.zeros(10), e_label="V", j_label="A", tafel_y_label="过电位（V）",
        potential_channel="V", current_channel="I", potential_formula="V",
        current_formula="I", e_eq=0.0, segment=seg,
    )
    return ComparisonItem(
        item_id="test::0", file_path=Path("/a.tdms"), file_name="a",
        segment_index=0, prepared=ps, fit=None,
        label="a-第1段", color="#2563eb",
    )


def test_rename_sets_file_name_and_derives_label():
    item = _make_item()
    item.rename("new_name")
    assert item.file_name == "new_name"
    assert item.label == "new_name-第1段"


def test_set_label_only_changes_label():
    item = _make_item()
    item.set_label("custom label")
    assert item.label == "custom label"
    assert item.file_name == "a"  # unchanged


def test_lsv_style_options_normalize_and_map_to_plot_kwargs():
    assert normalize_lsv_style("unknown") == "line_marker"
    assert lsv_plot_kwargs("line", linewidth=2.0, markersize=4.0)["marker"] is None
    assert lsv_plot_kwargs("scatter", linewidth=2.0, markersize=4.0)["linestyle"] == "None"
    mixed = lsv_plot_kwargs("line_marker", linewidth=2.0, markersize=4.0)
    assert mixed["marker"] == "o"
    assert mixed["linestyle"] == "-"


def test_comparison_display_point_limit_shrinks_for_many_items():
    from core.comparison import _comparison_point_limit

    assert _comparison_point_limit(1) >= _comparison_point_limit(20)
    assert _comparison_point_limit(20) == 250


def test_tafel_window_mask_keeps_fit_region_plus_twenty_percent_of_fit_points_each_side():
    selected = np.zeros(100, dtype=bool)
    selected[40:51] = True

    mask = tafel_window_mask(selected, True)

    assert np.flatnonzero(mask)[0] == 37
    assert np.flatnonzero(mask)[-1] == 53
    assert np.all(mask[selected])
    assert np.all(tafel_window_mask(selected, False))


def test_tafel_window_mask_uses_source_indices_not_sorted_positions():
    selected = np.zeros(100, dtype=bool)
    selected[70:81] = True
    source = np.arange(100)[::-1]

    mask = tafel_window_mask(selected, True, source)
    kept_source = source[mask]

    assert kept_source.min() == 16
    assert kept_source.max() == 32
    assert np.all(mask[selected])
