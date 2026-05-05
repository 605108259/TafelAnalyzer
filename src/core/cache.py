"""结果缓存：缓存键构建、载荷序列化、文件导出。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from core.types import ComparisonItem
from core.serialization import fit_to_dict, prepared_to_dict

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


def make_result_cache_key(
    *,
    tdms_path: Path,
    potential_formula: str,
    current_formula: str,
    e_eq: float,
    active_segment_index: int,
    selected_segment_indices: tuple[int, ...],
    min_window: int,
    max_window: int,
    eta_range: tuple[float, float] | None,
    logj_range: tuple[float, float] | None,
    min_r2: float,
    fit_priority: str,
) -> tuple:
    return (
        str(tdms_path),
        potential_formula,
        current_formula,
        round(float(e_eq), 12),
        int(active_segment_index),
        tuple(int(index) for index in selected_segment_indices),
        int(min_window),
        int(max_window),
        None if eta_range is None else tuple(round(float(v), 12) for v in eta_range),
        None if logj_range is None else tuple(round(float(v), 12) for v in logj_range),
        round(float(min_r2), 12),
        fit_priority,
    )


def cache_key_to_json(cache_key: tuple) -> list:
    data: list = []
    for item in cache_key:
        if isinstance(item, tuple):
            data.append(list(item))
        else:
            data.append(item)
    return data


def cache_key_from_json(cache_key: list) -> tuple:
    restored: list = []
    for item in cache_key:
        if isinstance(item, list):
            restored.append(tuple(item))
        else:
            restored.append(item)
    return tuple(restored)


def build_cache_payload(app: TafelAnalyzerApp) -> dict:
    from core.rendering import capture_axes_limits, capture_plot_view_state

    current_path = app._app_state.get("tdms_path")
    return {
        "selected_paths": [str(path) for path in app._app_state["selected_paths"]],
        "current_path": str(current_path) if current_path is not None else None,
        "file_ui_cache": app._app_state["file_ui_cache"],
        "current_result_keys": {
            file_key: cache_key_to_json(cache_key)
            for file_key, cache_key in app._app_state["current_result_keys"].items()
        },
        "result_cache": [
            {
                "key": cache_key_to_json(cache_key),
                "prepared": prepared_to_dict(cached["prepared"]),
                "fit": fit_to_dict(cached["fit"]) if cached.get("fit") is not None else None,
                "prepared_by_segment": {
                    str(index): prepared_to_dict(value)
                    for index, value in cached.get("prepared_by_segment", {}).items()
                },
                "fit_by_segment": {
                    str(index): fit_to_dict(value)
                    for index, value in cached.get("fit_by_segment", {}).items()
                },
                "fit_error_by_segment": {
                    str(index): value
                    for index, value in cached.get("fit_error_by_segment", {}).items()
                },
                "selected_segment_indices": list(cached.get("selected_segment_indices", [])),
                "active_segment_index": int(cached.get("active_segment_index", 0)),
                "view_state": cached.get("view_state"),
                "limits": cached.get("limits"),
            }
            for cache_key, cached in app._app_state["result_cache"].items()
        ],
        "comparison_items": [
            {
                "item_id": item.item_id,
                "file_path": str(item.file_path),
                "file_name": item.file_name,
                "segment_index": item.segment_index,
                "prepared": prepared_to_dict(item.prepared),
                "fit": fit_to_dict(item.fit) if item.fit is not None else None,
                "label": item.label,
                "color": item.color,
                "visible": item.visible,
            }
            for item in app._app_state.get("comparison_items", [])
        ],
    }


def export_cache_file(app: TafelAnalyzerApp, path: Path) -> Path:
    payload = build_cache_payload(app)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
