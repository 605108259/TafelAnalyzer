"""数据序列化：TafelFit / PreparedSeries / SegmentInfo ↔ dict。"""
from __future__ import annotations

import numpy as np

from core.data_cleaning import valid_measurement_mask
from core.types import PreparedSeries, SegmentInfo, TafelFit


def segment_to_dict(segment) -> dict:
    return {"index": int(segment.index), "start": int(segment.start), "end": int(segment.end)}


def segment_from_dict(data: dict) -> SegmentInfo:
    return SegmentInfo(index=int(data["index"]), start=int(data["start"]), end=int(data["end"]))


def prepared_to_dict(prepared: PreparedSeries) -> dict:
    return {
        "raw_e": prepared.raw_e.tolist(),
        "raw_j": prepared.raw_j.tolist(),
        "e": prepared.e.tolist(),
        "j": prepared.j.tolist(),
        "eta": prepared.eta.tolist(),
        "e_label": prepared.e_label,
        "j_label": prepared.j_label,
        "tafel_y_label": prepared.tafel_y_label,
        "potential_channel": prepared.potential_channel,
        "current_channel": prepared.current_channel,
        "potential_formula": prepared.potential_formula,
        "current_formula": prepared.current_formula,
        "e_eq": float(prepared.e_eq),
        "segment": segment_to_dict(prepared.segment),
    }


def prepared_from_dict(data: dict) -> PreparedSeries:
    raw_e = np.asarray(data["raw_e"], dtype=float)
    raw_j = np.asarray(data["raw_j"], dtype=float)
    e = np.asarray(data["e"], dtype=float)
    j = np.asarray(data["j"], dtype=float)
    e_eq = float(data["e_eq"])
    stored_eta = np.asarray(data["eta"], dtype=float)
    n = min(raw_e.size, raw_j.size, e.size, j.size, stored_eta.size)
    raw_e = raw_e[:n]
    raw_j = raw_j[:n]
    e = e[:n]
    j = j[:n]
    stored_eta = stored_eta[:n]
    valid_mask = valid_measurement_mask(raw_e, raw_j, e, j)
    raw_e = raw_e[valid_mask]
    raw_j = raw_j[valid_mask]
    e = e[valid_mask]
    j = j[valid_mask]
    stored_eta = stored_eta[valid_mask]
    eta = e_eq - e if e.shape == stored_eta.shape else stored_eta
    return PreparedSeries(
        raw_e=raw_e,
        raw_j=raw_j,
        e=e,
        j=j,
        eta=eta,
        e_label=str(data["e_label"]),
        j_label=str(data["j_label"]),
        tafel_y_label=str(data["tafel_y_label"]),
        potential_channel=str(data["potential_channel"]),
        current_channel=str(data["current_channel"]),
        potential_formula=str(data["potential_formula"]),
        current_formula=str(data["current_formula"]),
        e_eq=e_eq,
        segment=segment_from_dict(data["segment"]),
    )


def fit_to_dict(fit: TafelFit) -> dict:
    return {
        "slope_v_per_dec": float(fit.slope_v_per_dec),
        "intercept_v": float(fit.intercept_v),
        "r2": float(fit.r2),
        "x_log10_j": fit.x_log10_j.tolist(),
        "y_e": fit.y_e.tolist(),
        "selected_mask": fit.selected_mask.astype(bool).tolist(),
        "source_indices": fit.source_indices.astype(int).tolist(),
        "mode": fit.mode,
    }


def fit_from_dict(data: dict) -> TafelFit:
    x = np.asarray(data["x_log10_j"], dtype=float)
    y = np.asarray(data["y_e"], dtype=float)
    selected = np.asarray(data["selected_mask"], dtype=bool)
    source = np.asarray(data["source_indices"], dtype=int)
    n = min(x.size, y.size, selected.size, source.size)
    x = x[:n]
    y = y[:n]
    selected = selected[:n]
    source = source[:n]
    valid_mask = valid_measurement_mask(x, y)
    x = x[valid_mask]
    y = y[valid_mask]
    selected = selected[valid_mask]
    source = source[valid_mask]
    return TafelFit(
        slope_v_per_dec=float(data["slope_v_per_dec"]),
        intercept_v=float(data["intercept_v"]),
        r2=float(data["r2"]),
        x_log10_j=x,
        y_e=y,
        selected_mask=selected,
        source_indices=source,
        mode=str(data.get("mode", "auto")),
    )
