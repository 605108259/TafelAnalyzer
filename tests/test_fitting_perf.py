# tests/test_fitting_perf.py
import sys
from pathlib import Path
import numpy as np
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.fitting import _best_window_fit


def test_best_window_fit_correctness():
    """向量化后结果应与原始逻辑一致。"""
    np.random.seed(42)
    x = np.linspace(0, 10, 100)
    y = 2.5 * x + np.random.normal(0, 0.1, 100)
    start, end, slope, r2 = _best_window_fit(x, y, min_window=10, max_window=50)
    assert r2 > 0.99
    assert abs(slope - 2.5) < 0.1


def test_best_window_fit_large_data():
    """大数据量应能在合理时间内完成。"""
    np.random.seed(42)
    n = 2000
    x = np.linspace(0, 100, n)
    y = 3.0 * x + np.random.normal(0, 0.5, n)
    t0 = time.time()
    start, end, slope, r2 = _best_window_fit(x, y, min_window=20, max_window=200)
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"Too slow: {elapsed:.2f}s"
    assert r2 > 0.95
