"""Tests for core.formula — evaluate_formula."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.formula import evaluate_formula


def test_evaluate_formula_simple_channel():
    """简单通道引用应返回原始数据。"""
    channels = {"Vgs": np.array([1.0, 2.0, 3.0]), "Igs": np.array([0.1, 0.2, 0.3])}
    result = evaluate_formula(channels, "[Vgs]", ["Vgs"])
    assert list(result.values) == [1.0, 2.0, 3.0]


def test_evaluate_formula_arithmetic():
    """公式应支持基本算术运算。"""
    channels = {"Vgs": np.array([1.0, 2.0, 3.0])}
    result = evaluate_formula(channels, "-[Vgs]", ["Vgs"])
    assert list(result.values) == [-1.0, -2.0, -3.0]


def test_evaluate_formula_with_offset():
    """公式应支持常量偏移。"""
    channels = {"Vgs": np.array([1.0, 2.0, 3.0])}
    result = evaluate_formula(channels, "[Vgs]+0.23", ["Vgs"])
    assert abs(result.values[0] - 1.23) < 1e-10


def test_evaluate_formula_multiplication():
    """公式应支持乘法。"""
    channels = {"V": np.array([1.0, 2.0, 3.0])}
    result = evaluate_formula(channels, "[V]*2", ["V"])
    assert list(result.values) == [2.0, 4.0, 6.0]


def test_evaluate_formula_division():
    """公式应支持除法。"""
    channels = {"I": np.array([10.0, 20.0, 30.0])}
    result = evaluate_formula(channels, "[I]/10", ["I"])
    assert list(result.values) == [1.0, 2.0, 3.0]
