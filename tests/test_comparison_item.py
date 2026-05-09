import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.types import ComparisonItem, PreparedSeries, SegmentInfo


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
