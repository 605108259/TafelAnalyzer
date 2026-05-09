"""设置持久化（PySide6 版）：加载/保存应用设置，无 tkinter 依赖。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from core.types import COMPARISON_COLORS
from ui.state import DEFAULT_SCHEME_NAME, normalize_palette_scheme_name

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


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
    return {
        str(index): color
        for index, color in sorted(color_map.items())
        if _normalize_color_value(color) is not None
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
    app: TafelAnalyzerApp,
    scheme_name: str,
) -> dict[int, str]:
    scheme_name = _normalize_palette_scheme_name(scheme_name)
    schemes = app._app_state.setdefault("palette_schemes", {})
    colors = dict(schemes.get(scheme_name, {}))
    slot_counts = app._app_state.get("palette_scheme_slot_counts", {})
    slot_count = slot_counts.get(scheme_name, 8)
    for index in range(slot_count):
        if index not in colors:
            colors[index] = _default_segment_color(index)
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


# ── Load / Save ──────────────────────────────────────────────────────


def load_app_settings(app: TafelAnalyzerApp) -> None:
    try:
        if not APP_SETTINGS_PATH.exists():
            return
        payload = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

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
    app._app_state["saved_parameter_defaults"] = normalize_parameter_settings(
        payload.get("saved_parameter_defaults", {})
    )


def save_app_settings(app: TafelAnalyzerApp) -> None:
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
        "saved_parameter_defaults": normalize_parameter_settings(
            app._app_state.get("saved_parameter_defaults", {})
        ),
    }
    APP_SETTINGS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
