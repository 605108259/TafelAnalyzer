"""数据类型与常量定义。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

POTENTIAL_PREFERRED_NAMES = ["V", "E", "E(V)", "Vgs", "Potential", "potential"]
CURRENT_PREFERRED_NAMES = [
    "Igs/area",
    "j",
    "J",
    "i",
    "i(A/cm^2)",
    "CurrentDensity",
    "current_density",
    "I",
    "Igs",
    "Current",
    "current",
]
CHANNEL_REF_PATTERN = re.compile(r"\[([^\[\]]+)\]")
COR_DEFAULT_HEADERS = ["E(V)", "i(A/cm^2)", "T(s)"]


@dataclass(frozen=True)
class TafelFit:
    slope_v_per_dec: float
    intercept_v: float
    r2: float
    x_log10_j: np.ndarray
    y_e: np.ndarray
    selected_mask: np.ndarray
    source_indices: np.ndarray
    mode: str = "auto"

    @property
    def slope_mv_per_dec(self) -> float:
        return float(self.slope_v_per_dec * 1000.0)

    @property
    def selected_count(self) -> int:
        return int(np.count_nonzero(self.selected_mask))


@dataclass(frozen=True)
class SegmentInfo:
    index: int
    start: int
    end: int

    @property
    def length(self) -> int:
        return int(self.end - self.start)

    @property
    def label(self) -> str:
        return f"第{self.index + 1}段 | 点 {self.start + 1}-{self.end} | 长度 {self.length}"


@dataclass(frozen=True)
class FormulaResult:
    values: np.ndarray
    formula: str
    primary_channel: str
    references: tuple[str, ...]


@dataclass(frozen=True)
class PreparedSeries:
    raw_e: np.ndarray
    raw_j: np.ndarray
    e: np.ndarray
    j: np.ndarray
    eta: np.ndarray
    e_label: str
    j_label: str
    tafel_y_label: str
    potential_channel: str
    current_channel: str
    potential_formula: str
    current_formula: str
    e_eq: float
    segment: SegmentInfo


COMPARISON_COLORS = [
    "#2563eb", "#db2777", "#0891b2", "#16a34a",
    "#f59e0b", "#7c3aed", "#dc2626", "#0f766e",
    "#6366f1", "#ea580c", "#0d9488", "#a21caf",
]


@dataclass
class ComparisonItem:
    """跨文件对比列表中的一项"""
    item_id: str
    file_path: Path
    file_name: str
    segment_index: int
    prepared: PreparedSeries
    fit: TafelFit | None
    label: str
    color: str
    visible: bool = True


def _normalize_optional_range(
    value_range: tuple[float, float] | None,
) -> tuple[float, float] | None:
    if value_range is None:
        return None
    low, high = value_range
    return (float(low), float(high)) if float(low) <= float(high) else (float(high), float(low))
