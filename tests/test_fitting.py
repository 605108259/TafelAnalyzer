"""Tests for core.fitting — auto_tafel_fit, _best_window_fit, _build_cumulative, build_segment_infos."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.fitting import auto_tafel_fit, _best_window_fit, _build_cumulative, build_segment_infos


def test_auto_tafel_fit_perfect_linear():
    """完美线性数据应返回高 R² 拟合。"""
    # Tafel 横轴是 log10(|j|)，纵轴是 overpotential
    j = np.logspace(-6, -2, 100)  # 电流密度
    e_v = 0.12 * np.log10(j) + 0.3  # 斜率 0.12 V/dec
    fit = auto_tafel_fit(e_v, j, min_window=10, max_window=50)
    assert fit.r2 > 0.999
    assert abs(fit.slope_mv_per_dec - 120.0) < 5.0


def test_auto_tafel_fit_noisy_data():
    """含噪声数据应返回合理拟合。"""
    np.random.seed(42)
    j = np.logspace(-5, -1, 200)
    e_v = 0.06 * np.log10(j) + 0.2 + np.random.normal(0, 0.005, 200)
    fit = auto_tafel_fit(e_v, j, min_window=15, max_window=100)
    assert fit.r2 > 0.9
    assert 40.0 < abs(fit.slope_mv_per_dec) < 80.0


def test_best_window_fit_selects_best_window():
    """当 fit_priority='r2' 时应选择 R² 最高的窗口。"""
    x = np.linspace(0, 10, 100)
    y = 3.0 * x + 0.5
    start, end, slope, r2 = _best_window_fit(x, y, min_window=10, max_window=80)
    assert r2 > 0.999
    assert abs(slope - 3.0) < 0.01


def test_build_cumulative():
    """累积和应正确计算。"""
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    cum_x, cum_y, cum_xx, cum_xy, cum_yy = _build_cumulative(x, y)
    assert cum_x[0] == 0.0
    assert cum_x[1] == 1.0
    assert cum_x[3] == 6.0
    assert cum_y[3] == 15.0


def test_build_segment_infos_single_segment():
    """连续数据应识别为单个分段。"""
    channels = {"V": list(range(100))}
    infos = build_segment_infos(channels)
    assert len(infos) == 1
    assert infos[0].start == 0
    assert infos[0].end == 100


def test_build_segment_infos_with_jump():
    """含有大幅跳跃的数据应分割为多个分段。"""
    data = list(range(50)) + list(range(200, 250))
    channels = {"potential": data}
    infos = build_segment_infos(channels, "[potential]")
    assert len(infos) >= 2
