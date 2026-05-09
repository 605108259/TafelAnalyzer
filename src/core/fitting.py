"""Tafel 拟合与自动分段。

包含：
- 线性回归辅助函数（_r2_score, _linear_fit）
- 数据预处理（_prepare_xy）
- 最优窗口搜索（_best_window_fit, _expand_region）
- 自动/手动 Tafel 拟合（auto_tafel_fit, manual_tafel_fit）
- 自动分段检测（build_segment_infos, prepare_series）
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np

# 自动分段检测阈值
SEG_RANGE_TOLERANCE_FRAC = 1e-4  # 容差 = 值范围 × 此值
SEG_ABS_TOLERANCE = 1e-9         # 容差绝对最小值
SEG_JUMP_STEP_MULTIPLIER = 12.0  # 跳变阈值 = 典型步长 × 此值
SEG_JUMP_RANGE_FRAC = 0.25       # 跳变阈值 = 值范围 × 此值
SEG_JUMP_TOLERANCE_MULTIPLIER = 8.0  # 跳变阈值 = 容差 × 此值
SEG_ABS_JUMP = 1e-6              # 跳变阈值绝对最小值
VAR_EPSILON = 1e-30              # 方差归零判定
SLOPE_DEVIATION_FRAC = 0.6       # 扩展区域时斜率偏差上限（原斜率的倍数）
SLOPE_ABS_EPSILON = 1e-9         # 斜率比较绝对下限

from core.types import (
    POTENTIAL_PREFERRED_NAMES,
    CURRENT_PREFERRED_NAMES,
    FormulaResult,
    PreparedSeries,
    SegmentInfo,
    TafelFit,
    _normalize_optional_range,
)
from core.formula import evaluate_formula, normalize_formula


def _r2_score(y: np.ndarray, y_pred: np.ndarray) -> float:
    y_mean = float(np.mean(y))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    ss_res = float(np.sum((y - y_pred) ** 2))
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - (ss_res / ss_tot)


def _linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    r2 = _r2_score(y, y_pred)
    return float(slope), float(intercept), float(r2)


def _prepare_xy(
    e: np.ndarray,
    j: np.ndarray,
    *,
    eta_range: tuple[float, float] | None = None,
    logj_range: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    e = np.asarray(e, dtype=float).reshape(-1)
    j = np.asarray(j, dtype=float).reshape(-1)
    n = min(e.size, j.size)
    e = e[:n]
    j = j[:n]
    source_indices = np.arange(n, dtype=int)
    finite_mask = np.isfinite(e) & np.isfinite(j)
    e = e[finite_mask]
    j = j[finite_mask]
    source_indices = source_indices[finite_mask]
    j_abs = np.abs(j)
    positive_mask = j_abs > 0.0
    e = e[positive_mask]
    j_abs = j_abs[positive_mask]
    source_indices = source_indices[positive_mask]
    x = np.log10(j_abs)
    order = np.argsort(x)
    x = x[order]
    e = e[order]
    source_indices = source_indices[order]
    candidate_mask = np.ones_like(x, dtype=bool)
    eta_bounds = _normalize_optional_range(eta_range)
    if eta_bounds is not None:
        candidate_mask &= (e >= eta_bounds[0]) & (e <= eta_bounds[1])
    logj_bounds = _normalize_optional_range(logj_range)
    if logj_bounds is not None:
        candidate_mask &= (x >= logj_bounds[0]) & (x <= logj_bounds[1])
    return x, e, source_indices, candidate_mask


def _fit_from_selected(
    x: np.ndarray,
    y: np.ndarray,
    source_indices: np.ndarray,
    selected_mask: np.ndarray,
    mode: str,
    *,
    min_r2: float | None = None,
) -> TafelFit:
    if int(np.count_nonzero(selected_mask)) < 2:
        raise ValueError("用于拟合的点数不足，至少需要 2 个点")
    slope, intercept, r2 = _linear_fit(x[selected_mask], y[selected_mask])
    if min_r2 is not None and r2 < float(min_r2):
        raise ValueError(f"拟合结果 R²={r2:.6f} 低于最小限制 {float(min_r2):.6f}")
    return TafelFit(
        slope_v_per_dec=slope,
        intercept_v=intercept,
        r2=r2,
        x_log10_j=x,
        y_e=y,
        selected_mask=selected_mask,
        source_indices=source_indices,
        mode=mode,
    )


def _window_rank(r2: float, slope: float, window: int, fit_priority: str) -> tuple[float, float, int]:
    if fit_priority == "slope":
        return (abs(float(slope)), -float(r2), -int(window))
    if fit_priority == "r2":
        return (-float(r2), abs(float(slope)), -int(window))
    raise ValueError(f"未知拟合优先策略：{fit_priority}")


def _build_cumulative(x: np.ndarray, y: np.ndarray) -> list[np.ndarray]:
    n = int(x.size)
    cum_x = np.empty(n + 1)
    cum_y = np.empty(n + 1)
    cum_xx = np.empty(n + 1)
    cum_xy = np.empty(n + 1)
    cum_yy = np.empty(n + 1)
    cum_x[0] = cum_y[0] = cum_xx[0] = cum_xy[0] = cum_yy[0] = 0.0
    cum_x[1:] = np.cumsum(x)
    cum_y[1:] = np.cumsum(y)
    cum_xx[1:] = np.cumsum(x * x)
    cum_xy[1:] = np.cumsum(x * y)
    cum_yy[1:] = np.cumsum(y * y)
    return [cum_x, cum_y, cum_xx, cum_xy, cum_yy]


def _best_window_fit(
    x: np.ndarray,
    y: np.ndarray,
    min_window: int,
    max_window: int,
    *,
    min_r2: float | None = None,
    fit_priority: str = "r2",
) -> tuple[int, int, float, float]:
    cum_x, cum_y, cum_xx, cum_xy, cum_yy = _build_cumulative(x, y)
    n = int(x.size)
    best = None
    for window in range(min_window, max_window + 1):
        if window > n:
            break
        w = float(window)
        num_starts = n - window + 1
        starts = np.arange(num_starts)
        ends = starts + window

        sx = cum_x[ends] - cum_x[starts]
        sy = cum_y[ends] - cum_y[starts]
        sxx = cum_xx[ends] - cum_xx[starts]
        sxy = cum_xy[ends] - cum_xy[starts]
        syy = cum_yy[ends] - cum_yy[starts]

        var_x = w * sxx - sx * sx
        valid = np.abs(var_x) >= VAR_EPSILON

        if not np.any(valid):
            continue

        cov_xy = w * sxy - sx * sy
        slopes = np.where(valid, cov_xy / var_x, 0.0)
        var_y = w * syy - sy * sy
        r2 = np.where(
            valid,
            np.where(np.abs(var_y) < VAR_EPSILON, 1.0, (cov_xy * cov_xy) / (var_x * var_y)),
            0.0,
        )

        if min_r2 is not None:
            valid = valid & (r2 >= float(min_r2))
            if not np.any(valid):
                continue

        valid_indices = np.where(valid)[0]
        if valid_indices.size == 0:
            continue
        if fit_priority == "slope":
            best_local_idx = valid_indices[np.argmin(np.abs(slopes[valid_indices]))]
        else:
            best_local_idx = valid_indices[np.argmax(r2[valid_indices])]
        rank = _window_rank(float(r2[best_local_idx]), float(slopes[best_local_idx]), window, fit_priority)
        if best is None or rank < best[0]:
            best = (rank, int(best_local_idx), int(best_local_idx) + window, float(slopes[best_local_idx]), float(r2[best_local_idx]))

    if best is None:
        if min_r2 is not None:
            raise ValueError(f"未找到满足最小 R²={float(min_r2):.6f} 的 Tafel 区间")
        raise ValueError("数据点太少，无法进行 Tafel 区间识别")
    _, start, end, slope, r2 = best
    return start, end, slope, r2


def _expand_region(
    x: np.ndarray,
    y: np.ndarray,
    start: int,
    end: int,
    slope_v_per_dec: float,
    max_window: int,
    *,
    min_r2: float | None = None,
    fit_priority: str = "r2",
) -> tuple[int, int]:
    cum_x, cum_y, cum_xx, cum_xy, cum_yy = _build_cumulative(x, y)
    n = int(x.size)

    def _win(a: int, b: int) -> tuple[float, float]:
        w = float(b - a)
        sx = cum_x[b] - cum_x[a]
        sy = cum_y[b] - cum_y[a]
        sxx = cum_xx[b] - cum_xx[a]
        sxy = cum_xy[b] - cum_xy[a]
        syy = cum_yy[b] - cum_yy[a]
        var_x = w * sxx - sx * sx
        if abs(var_x) < VAR_EPSILON:
            return 0.0, 0.0
        cov_xy = w * sxy - sx * sy
        slope = cov_xy / var_x
        var_y = w * syy - sy * sy
        r2 = 1.0 if abs(var_y) < VAR_EPSILON else (cov_xy * cov_xy) / (var_x * var_y)
        return slope, r2

    _, best_r2 = _win(start, end)
    changed = True
    best_start, best_end = start, end
    best_rank = _window_rank(best_r2, slope_v_per_dec, best_end - best_start, fit_priority)
    while changed:
        changed = False
        improved = None
        candidates: list[tuple[int, int]] = []
        if best_start > 0 and (best_end - (best_start - 1)) <= max_window:
            candidates.append((best_start - 1, best_end))
        if best_end < n and ((best_end + 1) - best_start) <= max_window:
            candidates.append((best_start, best_end + 1))
        for candidate_start, candidate_end in candidates:
            candidate_slope, candidate_r2 = _win(candidate_start, candidate_end)
            if min_r2 is not None and candidate_r2 < float(min_r2):
                continue
            if math.isfinite(slope_v_per_dec):
                delta = abs(candidate_slope - slope_v_per_dec)
                limit = max(abs(slope_v_per_dec) * SLOPE_DEVIATION_FRAC, SLOPE_ABS_EPSILON)
                if delta > limit:
                    continue
            candidate_rank = _window_rank(
                candidate_r2,
                candidate_slope,
                candidate_end - candidate_start,
                fit_priority,
            )
            if improved is None or candidate_rank < improved[0]:
                improved = (candidate_rank, candidate_start, candidate_end, candidate_r2, candidate_slope)
        if improved is not None and improved[0] < best_rank:
            best_rank, best_start, best_end, best_r2, slope_v_per_dec = improved
            changed = True
    return best_start, best_end


def auto_tafel_fit(
    e_v: np.ndarray,
    j: np.ndarray,
    *,
    min_window: int = 6,
    max_window: int | None = None,
    eta_range: tuple[float, float] | None = None,
    logj_range: tuple[float, float] | None = None,
    min_r2: float | None = None,
    fit_priority: str = "r2",
) -> TafelFit:
    x, y, source_indices, candidate_mask = _prepare_xy(e_v, j, eta_range=eta_range, logj_range=logj_range)
    candidate_x = x[candidate_mask]
    candidate_y = y[candidate_mask]
    candidate_indices = np.flatnonzero(candidate_mask)
    n = int(candidate_x.size)
    if n < 2:
        raise ValueError("有效数据点不足，无法进行 Tafel 拟合")
    min_window = max(3, int(min_window))
    min_window = min(min_window, n)
    if max_window is None:
        max_window = min(30, n)
    max_window = max(min_window, min(int(max_window), n))
    start, end, slope, _ = _best_window_fit(
        candidate_x,
        candidate_y,
        min_window=min_window,
        max_window=max_window,
        min_r2=min_r2,
        fit_priority=fit_priority,
    )
    start, end = _expand_region(
        candidate_x,
        candidate_y,
        start,
        end,
        slope_v_per_dec=slope,
        max_window=max_window,
        min_r2=min_r2,
        fit_priority=fit_priority,
    )
    selected_mask = np.zeros_like(x, dtype=bool)
    selected_mask[candidate_indices[start:end]] = True
    return _fit_from_selected(x, y, source_indices, selected_mask, mode="auto", min_r2=min_r2)


def manual_tafel_fit(
    e_v: np.ndarray,
    j: np.ndarray,
    *,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    eta_range: tuple[float, float] | None = None,
    logj_range: tuple[float, float] | None = None,
    min_r2: float | None = None,
) -> TafelFit:
    x, y, source_indices, candidate_mask = _prepare_xy(e_v, j, eta_range=eta_range, logj_range=logj_range)
    if x.size < 2:
        raise ValueError("有效数据点不足，无法进行手动拟合")
    x_low, x_high = sorted((float(x_min), float(x_max)))
    y_low, y_high = sorted((float(y_min), float(y_max)))
    selected_mask = candidate_mask & (x >= x_low) & (x <= x_high) & (y >= y_low) & (y <= y_high)
    return _fit_from_selected(x, y, source_indices, selected_mask, mode="manual", min_r2=min_r2)


def _robust_value_span(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=float).reshape(-1)
    finite = finite[np.isfinite(finite)]
    if finite.size <= 1:
        return 0.0
    low, high = np.nanpercentile(finite, [5.0, 95.0])
    return max(0.0, float(high - low))


def _robust_step_size(diffs: np.ndarray) -> float:
    finite = np.abs(np.asarray(diffs, dtype=float).reshape(-1))
    finite = finite[np.isfinite(finite)]
    finite = finite[finite > 0.0]
    if finite.size == 0:
        return 0.0
    if finite.size >= 8:
        low, high = np.nanpercentile(finite, [10.0, 90.0])
        inlier = finite[(finite >= low) & (finite <= high)]
        if inlier.size:
            finite = inlier
    return float(np.median(finite))


def _build_segment_infos_from_values(
    values: np.ndarray,
    tolerance_ratio: float = 0.12,
    *,
    min_segment_length: int = 6,
) -> list[SegmentInfo]:
    signal = np.asarray(values, dtype=float).reshape(-1)
    total = int(signal.size)
    if total <= 1:
        return [SegmentInfo(index=0, start=0, end=total)]
    diffs = np.diff(signal)
    finite_diffs = diffs[np.isfinite(diffs)]
    if finite_diffs.size == 0:
        return [SegmentInfo(index=0, start=0, end=total)]
    typical_step = _robust_step_size(finite_diffs)
    value_range = _robust_value_span(signal)
    tolerance = max(
        typical_step * tolerance_ratio,
        value_range * SEG_RANGE_TOLERANCE_FRAC,
        SEG_ABS_TOLERANCE,
    )
    jump_threshold = max(
        typical_step * SEG_JUMP_STEP_MULTIPLIER,
        value_range * SEG_JUMP_RANGE_FRAC,
        tolerance * SEG_JUMP_TOLERANCE_MULTIPLIER,
        SEG_ABS_JUMP,
    )
    boundaries = [0]
    current_direction = 0
    for index, delta in enumerate(diffs, start=1):
        if not np.isfinite(delta) or abs(delta) <= tolerance:
            continue
        if abs(delta) >= jump_threshold:
            boundary = max(boundaries[-1] + 1, index)
            if (
                boundary < total
                and boundary > boundaries[-1]
                and (boundary - boundaries[-1]) >= max(2, int(min_segment_length))
            ):
                boundaries.append(boundary)
            current_direction = 0
            continue
        direction = 1 if delta > 0 else -1
        if current_direction == 0:
            current_direction = direction
            continue
        if direction != current_direction:
            boundary = max(boundaries[-1] + 1, index - 1)
            if (
                boundary < total
                and boundary > boundaries[-1]
                and (boundary - boundaries[-1]) >= max(2, int(min_segment_length))
            ):
                boundaries.append(boundary)
                current_direction = direction
    boundaries.append(total)
    if len(boundaries) >= 3 and (total - boundaries[-2]) < max(2, int(min_segment_length)):
        boundaries.pop(-2)
    segments: list[SegmentInfo] = []
    for segment_index, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        if end - start > 0:
            segments.append(SegmentInfo(index=segment_index, start=start, end=end))
    if not segments:
        segments.append(SegmentInfo(index=0, start=0, end=total))
    return segments


def build_segment_infos(
    channels: dict[str, np.ndarray],
    potential_formula: str | None = None,
) -> list[SegmentInfo]:
    potential_result = evaluate_formula(
        channels,
        potential_formula,
        POTENTIAL_PREFERRED_NAMES,
    )
    return _build_segment_infos_from_values(potential_result.values, min_segment_length=6)


def prepare_series(
    channels: dict[str, np.ndarray],
    *,
    potential_formula: str | None = None,
    current_formula: str | None = None,
    e_eq: float = 0.0,
    segment_index: int = 0,
    precomputed_segments: list[SegmentInfo] | None = None,
) -> PreparedSeries:
    normalized_potential = normalize_formula(channels, potential_formula, POTENTIAL_PREFERRED_NAMES)
    normalized_current = normalize_formula(channels, current_formula, CURRENT_PREFERRED_NAMES)
    segments = precomputed_segments if precomputed_segments is not None else build_segment_infos(channels, normalized_potential)
    if segment_index < 0 or segment_index >= len(segments):
        raise ValueError(f"分段序号超出范围：{segment_index + 1}，当前共 {len(segments)} 段")
    segment = segments[segment_index]
    potential_result = evaluate_formula(
        channels,
        normalized_potential,
        POTENTIAL_PREFERRED_NAMES,
        start=segment.start,
        end=segment.end,
    )
    current_result = evaluate_formula(
        channels,
        normalized_current,
        CURRENT_PREFERRED_NAMES,
        start=segment.start,
        end=segment.end,
    )
    raw_e = np.asarray(channels[potential_result.primary_channel], dtype=float).reshape(-1)[segment.start:segment.end]
    raw_j = np.asarray(channels[current_result.primary_channel], dtype=float).reshape(-1)[segment.start:segment.end]
    n = min(
        raw_e.size,
        raw_j.size,
        potential_result.values.size,
        current_result.values.size,
    )
    processed_e = np.asarray(potential_result.values[:n], dtype=float)
    eta = np.abs(processed_e - float(e_eq))
    return PreparedSeries(
        raw_e=np.asarray(raw_e[:n], dtype=float),
        raw_j=np.asarray(raw_j[:n], dtype=float),
        e=processed_e,
        j=np.asarray(current_result.values[:n], dtype=float),
        eta=eta,
        e_label=potential_result.formula,
        j_label=current_result.formula,
        tafel_y_label="过电位（V）",
        potential_channel=potential_result.primary_channel,
        current_channel=current_result.primary_channel,
        potential_formula=potential_result.formula,
        current_formula=current_result.formula,
        e_eq=float(e_eq),
        segment=SegmentInfo(index=segment.index, start=segment.start, end=segment.start + n),
    )
