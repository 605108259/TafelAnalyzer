"""设置持久化：加载/保存应用设置。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from core.cache import atomic_write_json, payload_hash
from core.comparison import normalize_lsv_style
from core.types import COMPARISON_COLORS
from ui.state import DEFAULT_SCHEME_NAME, normalize_palette_scheme_name


# ── Settings path ────────────────────────────────────────────────────


def _resolve_app_settings_path() -> Path:
    candidates: list[Path] = []
    for env_name in ("APPDATA", "LOCALAPPDATA"):
        base_dir = os.environ.get(env_name)
        if base_dir:
            candidates.append(Path(base_dir))
    candidates.append(Path.home())
    for base_dir in candidates:
        try:
            settings_dir = base_dir / "Tafel Analyzer"
            settings_dir.mkdir(parents=True, exist_ok=True)
            return settings_dir / "tdms_tafel_gui_settings.json"
        except OSError:
            continue
    return Path("tdms_tafel_gui_settings.json").resolve()


APP_SETTINGS_PATH = _resolve_app_settings_path()
HISTORY_CACHE_DIR = APP_SETTINGS_PATH.parent / "history_cache"


# ── Palette helpers (tkinter-free) ───────────────────────────────────


def _normalize_color_value(color: str | None) -> str | None:
    if not isinstance(color, str):
        return None
    text = color.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return None


def _default_segment_color(index: int) -> str:
    return COMPARISON_COLORS[int(index) % len(COMPARISON_COLORS)]


def _normalize_palette_scheme_name(name: str | None) -> str:
    return normalize_palette_scheme_name(name)


def _deserialize_segment_colors(raw: dict | None) -> dict[int, str]:
    colors: dict[int, str] = {}
    if not isinstance(raw, dict):
        return colors
    for key, value in raw.items():
        color = _normalize_color_value(value)
        if color is None:
            continue
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            colors[index] = color
    return colors


def _serialize_segment_colors(color_map: dict[int, str]) -> dict[str, str]:
    normalized: dict[int, str] = {}
    for raw_index, raw_color in color_map.items():
        color = _normalize_color_value(raw_color)
        if color is None:
            continue
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            normalized[index] = color
    return {
        str(index): normalized[index]
        for index in sorted(normalized)
    }


def _normalize_palette_schemes(
    raw: dict | None,
    legacy_palette: dict | None = None,
) -> dict[str, dict[int, str]]:
    schemes: dict[str, dict[int, str]] = {}
    if isinstance(raw, dict):
        for name, colors in raw.items():
            scheme_name = _normalize_palette_scheme_name(name)
            schemes[scheme_name] = _deserialize_segment_colors(colors)
    legacy_colors = _deserialize_segment_colors(legacy_palette)
    if legacy_colors:
        schemes.setdefault("默认方案", legacy_colors)
    if not schemes:
        schemes["默认方案"] = {}
    return schemes


def _normalize_palette_scheme_slot_counts(
    raw: dict | None,
    schemes: dict[str, dict[int, str]],
) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if isinstance(raw, dict):
        for name, count in raw.items():
            scheme_name = _normalize_palette_scheme_name(name)
            try:
                normalized[scheme_name] = max(0, int(count))
            except Exception:
                continue
    counts: dict[str, int] = {}
    for scheme_name, colors in schemes.items():
        highest = (max(colors.keys()) + 1) if colors else 0
        if scheme_name in normalized:
            counts[scheme_name] = max(normalized[scheme_name], highest)
        else:
            counts[scheme_name] = max(highest, 8)
    return counts


def _materialize_palette_scheme(
    app: Any,
    scheme_name: str,
) -> dict[str, str]:
    scheme_name = _normalize_palette_scheme_name(scheme_name)
    schemes = app._app_state.setdefault("palette_schemes", {})
    colors = {
        str(index): color
        for index, color in _deserialize_segment_colors(schemes.get(scheme_name, {})).items()
    }
    slot_counts = app._app_state.get("palette_scheme_slot_counts", {})
    slot_count = slot_counts.get(scheme_name, 8)
    for index in range(slot_count):
        if str(index) not in colors:
            colors[str(index)] = _default_segment_color(index)
    schemes[scheme_name] = colors
    slot_counts[scheme_name] = max(slot_count, len(colors))
    return colors


# ── Parameter settings ───────────────────────────────────────────────


def default_parameter_settings() -> dict[str, str]:
    return {
        "e_eq": "0",
        "window_range": "12-15",
        "eta_range": "",
        "logj_range": "",
        "min_r2": "0.95",
        "fit_priority": "斜率更低优先",
    }


def normalize_parameter_settings(raw: dict | None) -> dict[str, str]:
    settings = default_parameter_settings()
    if not isinstance(raw, dict):
        return settings
    for key in settings:
        value = raw.get(key)
        if value is None:
            continue
        settings[key] = str(value)
    if settings["fit_priority"] not in {"斜率更低优先", "R²优先"}:
        settings["fit_priority"] = "斜率更低优先"
    return settings


def normalize_project_history(raw: list | None, *, limit: int = 80) -> list[dict]:
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        cache_path = str(item.get("cache_path") or "").strip()
        if not cache_path or cache_path in seen:
            continue
        seen.add(cache_path)
        result.append({
            "id": str(item.get("id") or cache_path),
            "title": str(item.get("title") or "未命名项目"),
            "updated_at": str(item.get("updated_at") or ""),
            "cache_path": cache_path,
            "files": [str(path) for path in item.get("files", []) if str(path).strip()],
        })
        if len(result) >= limit:
            break
    return result


def load_project_history_from_cache_dir(*, limit: int = 80) -> list[dict]:
    if not HISTORY_CACHE_DIR.exists():
        return []
    entries: list[dict] = []
    # v2: single JSON files
    for cache_path in HISTORY_CACHE_DIR.glob("*.json"):
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        files = [str(path) for path in payload.get("selected_paths", []) if str(path).strip()]
        current_path = str(payload.get("current_path") or "").strip()
        title = cache_path.stem
        if not re.match(r"^\d{4}-\d{2}-\d{2} ", title) and current_path:
            title = Path(current_path).stem
        try:
            updated_at = cache_path.stat().st_mtime
        except OSError:
            updated_at = 0
        entries.append({
            "id": cache_path.stem,
            "title": title,
            "updated_at": updated_at,
            "cache_path": str(cache_path),
            "files": files,
        })
    # v3: directories with manifest.json
    for cache_dir in HISTORY_CACHE_DIR.iterdir():
        if not cache_dir.is_dir():
            continue
        manifest_path = cache_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
        files = [str(p) for p in manifest.get("selected_paths", []) if str(p).strip()]
        current_path = str(manifest.get("current_path") or "").strip()
        title = cache_dir.name
        if not re.match(r"^\d{4}-\d{2}-\d{2} ", title) and current_path:
            title = Path(current_path).stem
        try:
            updated_at = manifest_path.stat().st_mtime
        except OSError:
            updated_at = 0
        entries.append({
            "id": cache_dir.name,
            "title": title,
            "updated_at": updated_at,
            "cache_path": str(cache_dir),
            "files": files,
        })
    entries.sort(key=lambda item: item.get("updated_at", 0), reverse=True)
    normalized: list[dict] = []
    for item in entries[:limit]:
        timestamp = item.get("updated_at", 0)
        updated_text = ""
        if timestamp:
            from datetime import datetime
            updated_text = datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
        normalized.append({
            "id": str(item.get("id") or item.get("cache_path")),
            "title": str(item.get("title") or "未命名项目"),
            "updated_at": updated_text,
            "cache_path": str(item.get("cache_path")),
            "files": list(item.get("files", [])),
        })
    return normalized


# ── Load / Save ──────────────────────────────────────────────────────


def load_app_settings(app: Any) -> None:
    payload = {}
    try:
        if APP_SETTINGS_PATH.exists():
            payload = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    if payload:
        app._app_state["palette_schemes"] = _normalize_palette_schemes(
            payload.get("palette_schemes", {}),
            payload.get("saved_segment_palette", {}),
        )
        app._app_state["palette_scheme_slot_counts"] = _normalize_palette_scheme_slot_counts(
            payload.get("palette_scheme_slot_counts", {}),
            app._app_state["palette_schemes"],
        )
        for scheme_name in list(app._app_state["palette_schemes"].keys()):
            _materialize_palette_scheme(app, scheme_name)
        app._app_state["active_palette_scheme"] = _normalize_palette_scheme_name(
            payload.get("active_palette_scheme")
        )
    project_history = normalize_project_history(
        payload.get("project_history", payload.get("file_history", []))
    )
    if not project_history:
        project_history = load_project_history_from_cache_dir()
    app._app_state["project_history"] = project_history
    app._app_state["comparison_lsv_style"] = normalize_lsv_style(
        payload.get("comparison_lsv_style")
    )
    app._app_state["comparison_tafel_fit_window"] = bool(
        payload.get("comparison_tafel_fit_window", False)
    )
    app._app_state["saved_parameter_defaults"] = normalize_parameter_settings(
        payload.get("saved_parameter_defaults")
    )
    # Axis label overrides: persist renamed axis titles/labels globally
    raw_overrides = payload.get("axis_label_overrides")
    if isinstance(raw_overrides, dict):
        overrides = {
            str(k): str(v) for k, v in raw_overrides.items()
            if isinstance(k, str) and isinstance(v, str) and v.strip()
        }
        app._app_state["axis_label_overrides"] = overrides


def save_app_settings(app: Any) -> None:
    schemes = app._app_state.get("palette_schemes", {})
    slot_counts = app._app_state.get("palette_scheme_slot_counts", {})
    payload = {
        "palette_schemes": {
            name: _serialize_segment_colors(schemes.get(name, {}))
            for name in schemes
        },
        "palette_scheme_slot_counts": {
            name: slot_counts.get(name, 8)
            for name in schemes
        },
        "active_palette_scheme": _normalize_palette_scheme_name(
            app._app_state.get("active_palette_scheme")
        ),
        "project_history": normalize_project_history(
            app._app_state.get("project_history", [])
        ),
        "comparison_lsv_style": normalize_lsv_style(
            app._app_state.get("comparison_lsv_style")
        ),
        "comparison_tafel_fit_window": bool(
            app._app_state.get("comparison_tafel_fit_window", False)
        ),
        "saved_parameter_defaults": normalize_parameter_settings(
            app._app_state.get("saved_parameter_defaults")
        ),
        "axis_label_overrides": dict(
            app._app_state.get("axis_label_overrides", {})
        ),
    }
    new_hash = payload_hash(payload)
    if new_hash == app._app_state.get("_last_settings_hash"):
        return
    app._app_state["_last_settings_hash"] = new_hash
    atomic_write_json(APP_SETTINGS_PATH, payload, indent=2)
