"""Data sanitization helpers for measured electrochemical series."""
from __future__ import annotations

import numpy as np


def robust_inlier_mask(values: np.ndarray) -> np.ndarray:
    """Return finite, non-extreme points using robust distribution bounds.

    This is intentionally conservative for normal ramps, but removes isolated
    device/driver sentinels such as -1e10 embedded in otherwise volt-scale data.
    """
    arr = np.asarray(values, dtype=float).reshape(-1)
    finite = np.isfinite(arr)
    if int(np.count_nonzero(finite)) < 3:
        return finite

    sample = arr[finite]
    q1, q3 = np.nanpercentile(sample, [25.0, 75.0])
    iqr = float(q3 - q1)
    median = float(np.nanmedian(sample))
    mad = float(np.nanmedian(np.abs(sample - median)))
    scale_candidates = [
        value
        for value in (iqr / 1.349 if iqr > 0.0 else 0.0, mad * 1.4826 if mad > 0.0 else 0.0)
        if value > 0.0
    ]
    scale = min(scale_candidates) if scale_candidates else 0.0

    if scale <= 0.0:
        tolerance = max(abs(median) * 1e-9, 1e-12)
        return finite & (np.abs(arr - median) <= tolerance)

    threshold = max(50.0 * scale, abs(median) * 1e-9, 1e-12)
    return finite & (np.abs(arr - median) <= threshold)


def valid_measurement_mask(*arrays: np.ndarray) -> np.ndarray:
    """Combined mask for aligned arrays: finite and not isolated extremes."""
    if not arrays:
        return np.asarray([], dtype=bool)
    n = min(int(np.asarray(arr).size) for arr in arrays)
    mask = np.ones(n, dtype=bool)
    for arr in arrays:
        values = np.asarray(arr, dtype=float).reshape(-1)[:n]
        mask &= robust_inlier_mask(values)
    return mask
