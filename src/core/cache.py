"""结果缓存：缓存键构建、载荷序列化、文件导出。"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.types import ComparisonItem
from core.serialization import fit_to_dict, prepared_to_dict


FILE_FINGERPRINT_VERSION = "file-sha256-v1"
MISSING_FILE_FINGERPRINT_VERSION = "file-unavailable-v1"
PREPARED_SERIES_VERSION = "eta-eq-minus-e-v1"


def atomic_write_json(path: Path, payload: dict, *, indent: int | None = None) -> None:
    """Write JSON to *path* atomically: write to .tmp then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if indent is not None:
        content = json.dumps(payload, ensure_ascii=False, indent=indent)
    else:
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def payload_hash(payload: dict) -> str:
    """Deterministic SHA256 hash of a JSON-serializable dict."""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        PREPARED_SERIES_VERSION,
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


def build_cache_payload(app: Any) -> dict:
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


# ── v3 directory-based cache ─────────────────────────────────────────


def _blob_key(cache_key: tuple, segment_index: int) -> str:
    """Deterministic blob key from cache key + segment index."""
    raw = json.dumps(cache_key, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}_s{segment_index}"


def build_v3_manifest(app: Any) -> dict:
    """Project metadata, file list, chart view state."""
    from core.rendering import persist_current_plot_view_state
    persist_current_plot_view_state(app)
    current_path = app.state.files.current_path if hasattr(app, "state") else app._app_state.get("tdms_path")
    return {
        "cache_format_version": 3,
        "project_id": app._app_state.get("current_project_id"),
        "project_title": app._app_state.get("current_project_title"),
        "selected_paths": [str(p) for p in app._app_state["selected_paths"]],
        "current_path": str(current_path) if current_path else None,
        "current_result_keys": {
            file_key: cache_key_to_json(cache_key)
            for file_key, cache_key in app._app_state.get("current_result_keys", {}).items()
        },
        "chart_view_state": {
            "active_mode": app._app_state.get("active_chart_mode"),
            "single": app._app_state.get("single_plot_view_state"),
            "comparison": app._app_state.get("compare_plot_view_state"),
        },
    }


def build_v3_file_ui(app: Any) -> dict:
    """Per-file UI settings (formulas, params, colors, segment selections)."""
    return deepcopy(app._app_state["file_ui_cache"])


def build_v3_result_index(app: Any) -> dict:
    """Result cache index with references to prepared/fit blobs."""
    index: dict = {}
    for cache_key, cached in app._app_state["result_cache"].items():
        key_str = cache_key_to_json(cache_key)
        prepared_refs: dict[str, str] = {}
        fit_refs: dict[str, str] = {}
        for seg_idx in cached.get("prepared_by_segment", {}):
            prepared_refs[str(seg_idx)] = _blob_key(cache_key, int(seg_idx))
        for seg_idx in cached.get("fit_by_segment", {}):
            fit_refs[str(seg_idx)] = _blob_key(cache_key, int(seg_idx))
        index[json.dumps(key_str)] = {
            "key": key_str,
            "selected_segment_indices": list(cached.get("selected_segment_indices", [])),
            "active_segment_index": int(cached.get("active_segment_index", 0)),
            "prepared_refs": prepared_refs,
            "fit_refs": fit_refs,
            "fit_error_by_segment": {
                str(k): v for k, v in cached.get("fit_error_by_segment", {}).items()
            },
            "manual_fit_regions": {
                str(k): v for k, v in cached.get("manual_fit_regions", {}).items()
                if isinstance(v, dict)
            },
            "view_state": cached.get("view_state"),
        }
    return index


def build_v3_comparison(app: Any) -> list[dict]:
    """Comparison items with references to prepared/fit blobs."""
    items: list[dict] = []
    for item in app._app_state.get("comparison_items", []):
        cache_key = _result_key_for_file_segment(app, item.file_path, item.segment_index)
        result_key_ref = cache_key_to_json(cache_key) if cache_key is not None else None
        blob_k = _blob_key(cache_key, item.segment_index) if cache_key is not None else None
        items.append({
            "item_id": item.item_id,
            "file_path": str(item.file_path),
            "file_name": item.file_name,
            "segment_index": item.segment_index,
            "prepared_ref": blob_k,
            "fit_ref": blob_k,
            "result_key_ref": result_key_ref,
            "label": item.label,
            "color": item.color,
            "visible": item.visible,
        })
    return items


def _entry_has_segment(cached: dict, segment_index: int) -> bool:
    return (
        segment_index in cached.get("prepared_by_segment", {})
        or segment_index in cached.get("fit_by_segment", {})
    )


def _result_key_for_file_segment(app: Any, file_path: Path, segment_index: int) -> tuple | None:
    """Find the path-independent result cache key that covers file + segment."""
    result_cache = app._app_state.get("result_cache", {})
    mapped = app._app_state.get("current_result_keys", {}).get(str(file_path))
    if mapped is not None:
        cached = result_cache.get(mapped)
        if isinstance(cached, dict) and _entry_has_segment(cached, segment_index):
            return mapped

    fingerprint = file_fingerprint(file_path)
    for cache_key, cached in result_cache.items():
        if not isinstance(cached, dict) or not _entry_has_segment(cached, segment_index):
            continue
        identity = cache_key[0] if cache_key else None
        if isinstance(identity, tuple) and identity == fingerprint:
            return cache_key
        if isinstance(identity, list) and tuple(identity) == fingerprint:
            return cache_key
        if isinstance(identity, str) and str(Path(identity)) == str(file_path):
            return cache_key
    return None


def build_v3_blobs(app: Any) -> tuple[dict[str, dict], dict[str, dict]]:
    """Returns (prepared_blobs, fit_blobs) keyed by blob key."""
    prepared_blobs: dict[str, dict] = {}
    fit_blobs: dict[str, dict] = {}
    for cache_key, cached in app._app_state["result_cache"].items():
        for seg_idx, prepared in cached.get("prepared_by_segment", {}).items():
            blob_k = _blob_key(cache_key, int(seg_idx))
            prepared_blobs[blob_k] = prepared_to_dict(prepared)
        for seg_idx, fit in cached.get("fit_by_segment", {}).items():
            blob_k = _blob_key(cache_key, int(seg_idx))
            fit_blobs[blob_k] = fit_to_dict(fit)
    return prepared_blobs, fit_blobs


def write_v3_project_dir(project_dir: Path, manifest: dict, file_ui: dict,
                         result_index: dict, comparison: list[dict],
                         prepared_blobs: dict[str, dict],
                         fit_blobs: dict[str, dict],
                         *, _hashes: dict | None = None) -> dict[str, str]:
    """Write v3 directory structure atomically. Returns new hashes."""
    project_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir = project_dir / "prepared"
    fits_dir = project_dir / "fits"
    prepared_dir.mkdir(exist_ok=True)
    fits_dir.mkdir(exist_ok=True)

    new_hashes: dict[str, str] = {}
    old_hashes = _hashes or {}

    def _write_if_changed(rel_path: str, data: dict) -> None:
        h = payload_hash(data)
        new_hashes[rel_path] = h
        if h == old_hashes.get(rel_path):
            return
        atomic_write_json(project_dir / rel_path, data)

    _write_if_changed("manifest.json", manifest)
    _write_if_changed("file_ui.json", file_ui)
    _write_if_changed("result_index.json", result_index)
    _write_if_changed("comparison.json", {"items": comparison})

    for blob_key, blob_data in prepared_blobs.items():
        rel = f"prepared/{blob_key}.json"
        _write_if_changed(rel, blob_data)

    for blob_key, blob_data in fit_blobs.items():
        rel = f"fits/{blob_key}.json"
        _write_if_changed(rel, blob_data)

    # Clean up stale blobs
    _cleanup_stale_blobs(prepared_dir, set(prepared_blobs.keys()))
    _cleanup_stale_blobs(fits_dir, set(fit_blobs.keys()))

    return new_hashes


def _cleanup_stale_blobs(blob_dir: Path, valid_keys: set[str]) -> None:
    """Remove blob files that are no longer referenced."""
    try:
        for f in blob_dir.iterdir():
            if f.suffix == ".json" and f.stem not in valid_keys:
                f.unlink(missing_ok=True)
    except OSError:
        pass


def load_v3_project_dir(project_dir: Path) -> dict:
    """Load a v3 project directory into a v2-compatible payload dict."""
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    file_ui = json.loads((project_dir / "file_ui.json").read_text(encoding="utf-8"))
    result_index = json.loads((project_dir / "result_index.json").read_text(encoding="utf-8"))
    comparison_data = json.loads((project_dir / "comparison.json").read_text(encoding="utf-8"))
    prepared_dir = project_dir / "prepared"
    fits_dir = project_dir / "fits"

    # Rebuild result_cache with embedded data
    result_cache: list[dict] = []
    for key_str, entry in result_index.items():
        prepared_by_segment: dict[str, dict] = {}
        fit_by_segment: dict[str, dict] = {}
        for seg_str, ref in entry.get("prepared_refs", {}).items():
            blob_path = prepared_dir / f"{ref}.json"
            if blob_path.exists():
                prepared = json.loads(blob_path.read_text(encoding="utf-8"))
                if is_prepared_payload(prepared):
                    prepared_by_segment[seg_str] = prepared
        for seg_str, ref in entry.get("fit_refs", {}).items():
            blob_path = fits_dir / f"{ref}.json"
            if blob_path.exists():
                fit_by_segment[seg_str] = json.loads(blob_path.read_text(encoding="utf-8"))
        if not prepared_by_segment:
            continue
        active_seg = entry.get("active_segment_index", 0)
        result_cache.append({
            "key": entry["key"],
            "prepared": prepared_by_segment.get(str(active_seg), next(iter(prepared_by_segment.values()))),
            "fit": fit_by_segment.get(str(active_seg)),
            "prepared_by_segment": prepared_by_segment,
            "fit_by_segment": fit_by_segment,
            "fit_error_by_segment": entry.get("fit_error_by_segment", {}),
            "manual_fit_regions": entry.get("manual_fit_regions", {}),
            "selected_segment_indices": entry.get("selected_segment_indices", []),
            "active_segment_index": active_seg,
            "view_state": entry.get("view_state"),
        })

    # Rebuild comparison items with embedded data
    comparison_items: list[dict] = []
    for item in comparison_data.get("items", []):
        prepared_data = None
        fit_data = None
        result_entry = _result_index_entry(result_index, item.get("result_key_ref"))
        ref = item.get("prepared_ref")
        if not ref and result_entry:
            ref = result_entry.get("prepared_refs", {}).get(str(item.get("segment_index")))
        if ref:
            blob_path = prepared_dir / f"{ref}.json"
            if blob_path.exists():
                prepared_data = json.loads(blob_path.read_text(encoding="utf-8"))
                if not is_prepared_payload(prepared_data):
                    prepared_data = None
        ref = item.get("fit_ref")
        if not ref and result_entry:
            ref = result_entry.get("fit_refs", {}).get(str(item.get("segment_index")))
        if ref:
            blob_path = fits_dir / f"{ref}.json"
            if blob_path.exists():
                fit_data = json.loads(blob_path.read_text(encoding="utf-8"))
        comparison_items.append({
            "item_id": item["item_id"],
            "file_path": item["file_path"],
            "file_name": item["file_name"],
            "segment_index": item["segment_index"],
            "prepared": prepared_data,
            "fit": fit_data,
            "label": item.get("label", ""),
            "color": item.get("color", ""),
            "visible": item.get("visible", True),
        })

    return {
        "cache_format_version": 3,
        "selected_paths": manifest["selected_paths"],
        "current_path": manifest["current_path"],
        "chart_view_state": manifest["chart_view_state"],
        "file_ui_cache": file_ui,
        "current_result_keys": _load_v3_current_result_keys(manifest, result_index),
        "result_cache": result_cache,
        "comparison_items": comparison_items,
    }


def is_prepared_payload(data) -> bool:
    if not isinstance(data, dict):
        return False
    required = {
        "raw_e",
        "raw_j",
        "e",
        "j",
        "eta",
        "e_label",
        "j_label",
        "tafel_y_label",
        "potential_channel",
        "current_channel",
        "potential_formula",
        "current_formula",
        "e_eq",
        "segment",
    }
    return required.issubset(data)


def _result_index_entry(result_index: dict, key_ref) -> dict | None:
    if key_ref is None:
        return None
    if isinstance(key_ref, str):
        entry = result_index.get(key_ref)
        if isinstance(entry, dict):
            return entry
        try:
            key_ref = json.loads(key_ref)
        except (TypeError, ValueError):
            return None
    if isinstance(key_ref, list):
        for candidate in (
            json.dumps(key_ref),
            json.dumps(key_ref, separators=(",", ":")),
        ):
            entry = result_index.get(candidate)
            if isinstance(entry, dict):
                return entry
        for entry in result_index.values():
            if isinstance(entry, dict) and entry.get("key") == key_ref:
                return entry
    return None


def _load_v3_current_result_keys(manifest: dict, result_index: dict) -> dict:
    current = manifest.get("current_result_keys")
    if isinstance(current, dict) and current:
        return current

    derived: dict[str, list] = {}
    selected_paths = [Path(path) for path in manifest.get("selected_paths", [])]
    used: set[str] = set()
    for path in selected_paths:
        match_key: list | None = None
        for index_key, entry in result_index.items():
            if index_key in used or not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if not isinstance(key, list) or not key:
                continue
            identity = key[0]
            if isinstance(identity, str) and str(Path(identity)) == str(path):
                match_key = key
            elif (
                isinstance(identity, list)
                and len(identity) >= 2
                and str(identity[1]).lower() == path.name.lower()
            ):
                match_key = key
            if match_key is not None:
                derived[str(path)] = match_key
                used.add(index_key)
                break
    return derived
