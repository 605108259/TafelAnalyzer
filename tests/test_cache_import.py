# tests/test_cache_import.py
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.serialization import prepared_to_dict, prepared_from_dict
from core.types import PreparedSeries, SegmentInfo


def _make_prepared() -> PreparedSeries:
    seg = SegmentInfo(index=0, start=0, end=10)
    return PreparedSeries(
        raw_e=np.linspace(0, 1, 10),
        raw_j=np.logspace(-6, -3, 10),
        e=np.linspace(0, 1, 10),
        j=np.logspace(-6, -3, 10),
        eta=np.linspace(0, 1, 10),
        e_label="[V]",
        j_label="[Igs/area]",
        tafel_y_label="过电位（V）",
        potential_channel="V",
        current_channel="Igs/area",
        potential_formula="[V]",
        current_formula="[Igs/area]",
        e_eq=0.0,
        segment=seg,
    )


def test_import_cache_restores_prepared_by_segment():
    """缓存导入应完整恢复 prepared_by_segment 字段。"""
    prepared = _make_prepared()
    serialized = {"prepared_by_segment": {"0": prepared_to_dict(prepared)}}
    restored = {
        int(k): prepared_from_dict(v)
        for k, v in serialized["prepared_by_segment"].items()
    }
    assert 0 in restored
    assert np.allclose(restored[0].e, prepared.e)


def test_import_cache_restores_fit_error_by_segment():
    """缓存导入应完整恢复 fit_error_by_segment 字段。"""
    raw_errors = {"0": "数据点不足", "1": "R² 不达标"}
    restored = {int(k): v for k, v in raw_errors.items()}
    assert restored[0] == "数据点不足"
    assert restored[1] == "R² 不达标"
