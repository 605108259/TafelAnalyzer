"""结果缓存：缓存键构建、载荷序列化、文件导出。"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from core.types import ComparisonItem
from core.serialization import fit_to_dict, prepared_to_dict

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


FILE_FINGERPRINT_VERSION = "file-sha256-v1"
MISSING_FILE_FINGERPRINT_VERSION = "file-unavailable-v1"


@lru_cache(maxsize=512)
def _file_fingerprint_for_stat(
    resolved_path: str,
    file_name: str,
    size: int,
    mtime_ns: int,
    ctime_ns: int,
) -> tuple:
    digest = hashlib.sha256()
    with Path(resolved_path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return (
        FILE_FINGERPRINT_VERSION,
        file_name.lower(),
        int(size),
        digest.hexdigest(),
    )


def file_fingerprint(path: Path) -> tuple:
    """Return a stable, path-independent file identity for cache keys.

    The content digest is cached by file path and stat signature so repeated
    autosaves do not re-read large data files while the file is unchanged.
    """
    file_path = Path(path)
    try:
        stat = file_path.stat()
    except OSError:
        return (MISSING_FILE_FINGERPRINT_VERSION, file_path.name.lower())

    try:
        resolved_path = str(file_path.resolve(strict=False))
    except OSError:
        resolved_path = str(file_path)

    return _file_fingerprint_for_stat(
        resolved_path,
        file_path.name,
        int(stat.st_size),
        int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
        int(getattr(stat, "st_ctime_ns", int(stat.st_ctime * 1_000_000_000))),
    )


def make_result_cache_key(
    *,
    tdms_path: Path,
    potential_formula: str,
    current_formula: str,
    e_eq: float,
    selected_segment_indices: tuple[int, ...],
    min_window: int,
    max_window: int,
    eta_range: tuple[float, float] | None,
    logj_range: tuple[float, float] | None,
    min_r2: float,
    fit_priority: str,
) -> tuple:
    return (
        file_fingerprint(tdms_path),
        potential_formula,
        current_formula,
        round(float(e_eq), 12),
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
    from core.rendering import persist_current_plot_view_state

    persist_current_plot_view_state(app)

    current_path = app.state.files.current_path if hasattr(app, "state") else app._app_state.get("tdms_path")
    return {
        "cache_format_version": 2,
        "selected_paths": [str(path) for path in app._app_state["selected_paths"]],
        "current_path": str(current_path) if current_path is not None else None,
        "chart_view_state": {
            "active_mode": app._app_state.get("active_chart_mode"),
            "single": app._app_state.get("single_plot_view_state"),
            "comparison": app._app_state.get("compare_plot_view_state"),
        },
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
                "manual_fit_regions": {
                    str(index): value
                    for index, value in cached.get("manual_fit_regions", {}).items()
                    if isinstance(value, dict)
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
