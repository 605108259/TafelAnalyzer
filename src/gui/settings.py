"""设置持久化：加载/保存应用设置。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from gui.widgets import set_entry_text
from gui import palette as p

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


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


def current_file_key(app: TafelAnalyzerApp) -> str | None:
    path = app._app_state.get("tdms_path")
    return str(path) if path is not None else None


def find_label_by_path(app: TafelAnalyzerApp, path: Path | None) -> str | None:
    if path is None:
        return None
    for label, target in app._app_state["path_lookup"].items():
        if target == path:
            return label
    return None


def get_segment_selection_text(app: TafelAnalyzerApp) -> str:
    from gui.widgets import segment_selection_text
    return segment_selection_text(app._app_state.get("selected_segment_indices", []))


def default_parameter_settings() -> dict[str, str]:
    return {
        "e_eq": "0",
        "window_range": "12-15",
        "eta_range": "",
        "logj_range": "",
        "min_r2": "0.95",
        "fit_priority": "斜率更低优先",
    }


def normalize_parameter_settings(app: TafelAnalyzerApp, raw: dict | None) -> dict[str, str]:
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


def collect_parameter_settings_from_form(app: TafelAnalyzerApp) -> dict[str, str]:
    return {
        "e_eq": app.entry_eeq.get().strip(),
        "window_range": app.entry_window_range.get().strip(),
        "eta_range": app.entry_eta_range.get().strip(),
        "logj_range": app.entry_logj_range.get().strip(),
        "min_r2": app.entry_min_r2.get().strip(),
        "fit_priority": app.combo_fit_priority.get().strip() or "斜率更低优先",
    }


def apply_parameter_settings_to_form(app: TafelAnalyzerApp, settings: dict[str, str]) -> None:
    set_entry_text(app.entry_eeq, settings.get("e_eq", "0"))
    set_entry_text(app.entry_window_range, settings.get("window_range", "12-15"))
    set_entry_text(app.entry_eta_range, settings.get("eta_range", ""))
    set_entry_text(app.entry_logj_range, settings.get("logj_range", ""))
    set_entry_text(app.entry_min_r2, settings.get("min_r2", "0.95"))
    app.combo_fit_priority.set(settings.get("fit_priority", "斜率更低优先"))


def persist_parameter_settings(app: TafelAnalyzerApp) -> None:
    app._app_state["saved_parameter_defaults"] = normalize_parameter_settings(app, collect_parameter_settings_from_form(app))
    save_app_settings(app)


def load_app_settings(app: TafelAnalyzerApp) -> None:
    try:
        if not APP_SETTINGS_PATH.exists():
            return
        payload = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    app._app_state["palette_schemes"] = p.normalize_palette_schemes(
        app, payload.get("palette_schemes", {}),
        payload.get("saved_segment_palette", {}),
    )
    app._app_state["palette_scheme_slot_counts"] = p.normalize_palette_scheme_slot_counts(
        app, payload.get("palette_scheme_slot_counts", {}),
        app._app_state["palette_schemes"],
    )
    materialized = False
    for scheme_name in list(app._app_state["palette_schemes"].keys()):
        original_colors = dict(app._app_state["palette_schemes"].get(scheme_name, {}))
        filled_colors = p.materialize_palette_scheme(app, scheme_name)
        if filled_colors != original_colors:
            materialized = True
    app._app_state["active_palette_scheme"] = p.normalize_palette_scheme_name(
        payload.get("active_palette_scheme")
    )
    p.refresh_palette_scheme_options(app, preferred=app._app_state["active_palette_scheme"])
    app._app_state["saved_parameter_defaults"] = normalize_parameter_settings(app, payload.get("saved_parameter_defaults", {}))
    apply_parameter_settings_to_form(app, app._app_state["saved_parameter_defaults"])
    if materialized:
        save_app_settings(app)


def save_app_settings(app: TafelAnalyzerApp) -> None:
    payload = {
        "palette_schemes": {
            name: p.serialize_segment_colors(app, p.get_palette_scheme_colors(app, name, include_defaults=True))
            for name in app._app_state.get("palette_schemes", {}).keys()
        },
        "palette_scheme_slot_counts": {
            name: p.palette_scheme_slot_count(app, name)
            for name in app._app_state.get("palette_schemes", {}).keys()
        },
        "active_palette_scheme": p.normalize_palette_scheme_name(app._app_state.get("active_palette_scheme")),
        "saved_parameter_defaults": normalize_parameter_settings(app, app._app_state.get("saved_parameter_defaults", {})),
    }
    APP_SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
