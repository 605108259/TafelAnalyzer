from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.cache import (  # noqa: E402
    build_cache_payload,
    build_v3_blobs,
    build_v3_comparison,
    build_v3_file_ui,
    build_v3_manifest,
    build_v3_result_index,
    cache_key_from_json,
    is_prepared_payload,
    load_v3_project_dir,
    make_result_cache_key,
    write_v3_project_dir,
)
from core.comparison import comparison_item_id, normalize_lsv_style, tafel_window_mask  # noqa: E402
from core.export import export_fit_npz, export_processed_txt, export_txt  # noqa: E402
from core.fitting import (  # noqa: E402
    auto_tafel_fit,
    build_segment_infos,
    manual_tafel_fit,
    prepare_full_series,
    prepare_series_from_full,
)
from core.formula import normalize_formula  # noqa: E402
from core.readers import read_data_all_channels  # noqa: E402
from core.rendering import clean_fit_plot_data, compute_tafel_points, valid_fit_source_indices  # noqa: E402
from core.serialization import fit_from_dict, prepared_from_dict  # noqa: E402
from core.theme import MPL_RC  # noqa: E402
from core.types import (  # noqa: E402
    COMPARISON_COLORS,
    CURRENT_PREFERRED_NAMES,
    POTENTIAL_PREFERRED_NAMES,
    ComparisonItem,
)
from core.utils import apply_matplotlib_cjk, parse_range_text, pick_channel_name, priority_label_to_key  # noqa: E402
from ui.settings import (  # noqa: E402
    HISTORY_CACHE_DIR,
    load_app_settings,
    load_project_history_from_cache_dir,
    save_app_settings,
)
from ui.state import AppState, create_initial_state  # noqa: E402

apply_matplotlib_cjk(plt)


def _json_safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _range_or_none(text: str, label: str):
    return parse_range_text(text or "", label, allow_empty=True)


def _priority_key(label_or_key: str) -> str:
    text = str(label_or_key or "").strip()
    if text in {"slope", "r2"}:
        return text
    return priority_label_to_key(text)


class _NoopCanvas:
    def draw_idle(self) -> None:
        return None


class _ToolbarSnapshot:
    def __init__(self, service: "WebBackend"):
        self.service = service

    def get_formulas(self) -> tuple[str, str]:
        return self.service.formulas()

    def get_params(self) -> dict:
        return dict(self.service.params)


class WebBackend:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._app_state = create_initial_state()
        self.state = AppState(self._app_state)
        self.params = {
            "e_eq": "0",
            "window_range": "12-15",
            "eta_range": "",
            "logj_range": "",
            "min_r2": "0.95",
            "fit_priority": "slope",
        }
        self._app_state["app_version"] = "web"
        self.fig = plt.figure(figsize=(12, 5.4), dpi=150)
        self.canvas = _NoopCanvas()
        self.toolbar = _ToolbarSnapshot(self)
        self._current_png = ""
        self._current_project_hashes: dict | None = None
        try:
            load_app_settings(self)
            saved = self._app_state.get("saved_parameter_defaults") or {}
            self.params.update({k: str(v) for k, v in saved.items() if k in self.params})
        except Exception:
            self._app_state["project_history"] = load_project_history_from_cache_dir()

    def formulas(self) -> tuple[str, str]:
        path = self.state.files.current_path
        entry = self._app_state.setdefault("file_ui_cache", {}).get(str(path), {}) if path else {}
        return (
            str(entry.get("potential_formula") or ""),
            str(entry.get("current_formula") or ""),
        )

    def snapshot(self) -> dict:
        with self.lock:
            current = self.state.files.current_path
            return {
                "selected_paths": [str(p) for p in self._app_state.get("selected_paths", [])],
                "current_path": str(current) if current else None,
                "files": [
                    {
                        "path": str(path),
                        "name": self.state.files.display_name(path),
                        "exists": Path(path).exists(),
                    }
                    for path in self._app_state.get("selected_paths", [])
                ],
                "channels": list((self._app_state.get("channels") or {}).keys()),
                "formulas": dict(zip(("potential", "current"), self.formulas())),
                "params": dict(self.params),
                "segments": self._segments_payload(),
                "active_segment_index": int(self._app_state.get("active_segment_index", 0)),
                "selected_segment_indices": list(self._app_state.get("selected_segment_indices", [])),
                "fits": self._fits_payload(),
                "comparison_items": self._comparison_payload(),
                "comparison_mode": bool(self._app_state.get("comparison_mode", False)),
                "comparison_lsv_style": self._app_state.get("comparison_lsv_style", "line_marker"),
                "comparison_tafel_fit_window": bool(self._app_state.get("comparison_tafel_fit_window", False)),
                "chart_png": self._current_png,
                "status": self._app_state.get("status", "ready"),
                "history": self._app_state.get("project_history", []),
            }

    def _segments_payload(self) -> list[dict]:
        selected = {int(i) for i in self._app_state.get("selected_segment_indices", [])}
        colors = self._app_state.get("segment_colors", {})
        errors = self._app_state.get("fit_error_by_segment", {})
        return [
            {
                "index": int(seg["index"]),
                "label": str(seg.get("label") or f"Segment {int(seg['index']) + 1}"),
                "selected": int(seg["index"]) in selected,
                "color": colors.get(int(seg["index"]), COMPARISON_COLORS[int(seg["index"]) % len(COMPARISON_COLORS)]),
                "has_fit": int(seg["index"]) in self._app_state.get("fit_by_segment", {}),
                "error": errors.get(int(seg["index"])),
            }
            for seg in self._app_state.get("segments", [])
        ]

    def _fits_payload(self) -> dict:
        payload = {}
        for index, fit in self._app_state.get("fit_by_segment", {}).items():
            payload[str(index)] = {
                "slope_mv_per_dec": fit.slope_mv_per_dec,
                "r2": fit.r2,
                "selected_count": fit.selected_count,
                "mode": fit.mode,
            }
        return payload

    def _comparison_payload(self) -> list[dict]:
        return [
            {
                "item_id": item.item_id,
                "file_path": str(item.file_path),
                "file_name": item.file_name,
                "segment_index": item.segment_index,
                "label": item.display_label,
                "color": item.color,
                "visible": item.visible,
                "slope_mv_per_dec": item.fit.slope_mv_per_dec if item.fit else None,
                "r2": item.fit.r2 if item.fit else None,
            }
            for item in self._app_state.get("comparison_items", [])
        ]

    def load_files(self, paths: list[str]) -> dict:
        with self.lock:
            clean = [Path(p) for p in paths if p and Path(p).exists()]
            if not clean:
                raise ValueError("No readable files were selected.")
            if not self._app_state.get("selected_paths"):
                self._begin_new_project()
            self.state.files.merge_paths(clean)
            self._load_file(clean[0])
            self.autosave()
            return self.snapshot()

    def select_file(self, path: str) -> dict:
        with self.lock:
            target = Path(path)
            if target not in self._app_state.get("selected_paths", []):
                raise ValueError("File is not part of the current project.")
            self._load_file(target)
            return self.snapshot()

    def remove_file(self, path: str) -> dict:
        with self.lock:
            target = Path(path)
            self.state.files.remove_path(target)
            self.state.comparison.remove_file_items(target)
            remaining = self._app_state.get("selected_paths", [])
            if remaining:
                self._load_file(remaining[0])
            else:
                self.state.reset_current_file()
                self._current_png = ""
            self.autosave()
            return self.snapshot()

    def set_formulas(self, potential: str, current: str) -> dict:
        with self.lock:
            path = self.state.files.current_path
            if path is None:
                raise ValueError("No file is loaded.")
            entry = self._app_state.setdefault("file_ui_cache", {}).setdefault(str(path), {})
            entry["potential_formula"] = str(potential or "")
            entry["current_formula"] = str(current or "")
            self._load_file(path)
            self.autosave()
            return self.snapshot()

    def set_params(self, params: dict) -> dict:
        with self.lock:
            for key in self.params:
                if key in params:
                    self.params[key] = str(params[key])
            path = self.state.files.current_path
            if path is not None:
                entry = self._app_state.setdefault("file_ui_cache", {}).setdefault(str(path), {})
                entry.update(self.params)
            self.autosave()
            return self.snapshot()

    def _load_file(self, path: Path) -> None:
        channels = read_data_all_channels(path)
        entry = self._app_state.setdefault("file_ui_cache", {}).setdefault(str(path), {})
        pot = str(entry.get("potential_formula") or "")
        cur = str(entry.get("current_formula") or "")
        pot = self._valid_or_default_formula(channels, pot, POTENTIAL_PREFERRED_NAMES)
        cur = self._valid_or_default_formula(channels, cur, CURRENT_PREFERRED_NAMES)
        entry["potential_formula"] = pot
        entry["current_formula"] = cur
        self.params.update({k: str(entry[k]) for k in self.params if k in entry})
        segments = build_segment_infos(channels, pot)
        colors = {}
        cached_colors = entry.get("segment_colors") if isinstance(entry.get("segment_colors"), dict) else {}
        for seg in segments:
            colors[seg.index] = str(cached_colors.get(str(seg.index)) or COMPARISON_COLORS[seg.index % len(COMPARISON_COLORS)])
        self.state.analysis.begin_file_load(path)
        self.state.analysis.apply_loaded_file(channels=channels, segment_infos=segments, segment_colors=colors)
        self._app_state["_precomputed_segments"] = segments
        if isinstance(entry.get("selected_segment_indices"), list):
            self._app_state["selected_segment_indices"] = [int(i) for i in entry["selected_segment_indices"] if int(i) < len(segments)]
        if "active_segment_index" in entry:
            self._app_state["active_segment_index"] = int(entry.get("active_segment_index") or 0)
        cache_key = self._app_state.get("current_result_keys", {}).get(str(path))
        if isinstance(cache_key, list):
            cache_key = cache_key_from_json(cache_key)
        cached = self._app_state.get("result_cache", {}).get(cache_key)
        if isinstance(cached, dict):
            self._restore_result_cache_entry(cache_key, cached)
        self._app_state["status"] = f"Loaded {path.name}"
        self.render_single()

    def _valid_or_default_formula(self, channels: dict, formula: str, preferred: list[str]) -> str:
        if formula:
            try:
                return normalize_formula(channels, formula, preferred)
            except Exception:
                pass
        return f"[{pick_channel_name(channels, preferred)}]"

    def run_fit(self, force: bool = False) -> dict:
        with self.lock:
            channels = self._app_state.get("channels")
            path = self.state.files.current_path
            if channels is None or path is None:
                raise ValueError("No file is loaded.")
            pot, cur = self.formulas()
            selected = [int(i) for i in self._app_state.get("selected_segment_indices", [])]
            if not selected:
                raise ValueError("No segments are selected.")
            window_min, window_max, eta_range, logj_range, min_r2, fit_priority, e_eq = self._fit_params()
            cache_key = make_result_cache_key(
                tdms_path=path,
                potential_formula=pot,
                current_formula=cur,
                e_eq=e_eq,
                selected_segment_indices=tuple(selected),
                min_window=window_min,
                max_window=window_max,
                eta_range=eta_range,
                logj_range=logj_range,
                min_r2=min_r2,
                fit_priority=fit_priority,
            )
            cached = self._app_state.get("result_cache", {}).get(cache_key)
            if cached is not None and not force:
                self._restore_result_cache_entry(cache_key, cached)
                self._app_state["status"] = "Restored fit from compatible project cache."
                self.render_single()
                return self.snapshot()
            full_data, all_segments = prepare_full_series(
                channels,
                potential_formula=pot,
                current_formula=cur,
                e_eq=e_eq,
                precomputed_segments=self._app_state.get("_precomputed_segments"),
            )
            prepared_map = {}
            fit_map = {}
            error_map = {}
            for seg_idx in selected:
                try:
                    prepared = prepare_series_from_full(full_data, all_segments[seg_idx])
                    prepared_map[seg_idx] = prepared
                    fit_map[seg_idx] = auto_tafel_fit(
                        prepared.eta,
                        prepared.j,
                        min_window=window_min,
                        max_window=window_max,
                        min_r2=min_r2,
                        fit_priority=fit_priority,
                        eta_range=eta_range,
                        logj_range=logj_range,
                    )
                except Exception as exc:
                    error_map[seg_idx] = str(exc)
            active = self.state.analysis.merge_fit_results(
                prepared_map=prepared_map,
                fit_map=fit_map,
                error_map=error_map,
            )
            if active is not None:
                self._app_state["active_segment_index"] = int(active.segment.index)
            self._remember_result_cache(cache_key)
            self._app_state["status"] = f"Fit completed: {len(fit_map)} ok, {len(error_map)} failed."
            self.render_single()
            self.autosave()
            return self.snapshot()

    def manual_fit(self, region: dict) -> dict:
        with self.lock:
            active = int(self._app_state.get("active_segment_index", 0))
            prepared = self._app_state.get("prepared_by_segment", {}).get(active)
            if prepared is None:
                self.run_fit(force=False)
                prepared = self._app_state.get("prepared_by_segment", {}).get(active)
            if prepared is None:
                raise ValueError("The active segment has no prepared data.")
            _window_min, _window_max, eta_range, logj_range, min_r2, _fit_priority, _e_eq = self._fit_params()
            fit = manual_tafel_fit(
                prepared.eta,
                prepared.j,
                x_min=float(region["x_min"]),
                x_max=float(region["x_max"]),
                y_min=float(region["y_min"]),
                y_max=float(region["y_max"]),
                eta_range=eta_range,
                logj_range=logj_range,
                min_r2=min_r2,
            )
            self._app_state.setdefault("fit_by_segment", {})[active] = fit
            self._app_state.setdefault("fit_error_by_segment", {}).pop(active, None)
            self._app_state.setdefault("manual_fit_regions", {})[active] = {
                "x_min": min(float(region["x_min"]), float(region["x_max"])),
                "x_max": max(float(region["x_min"]), float(region["x_max"])),
                "y_min": min(float(region["y_min"]), float(region["y_max"])),
                "y_max": max(float(region["y_min"]), float(region["y_max"])),
            }
            self._app_state["fit"] = fit
            self._remember_current_result_cache()
            self._app_state["status"] = f"Manual fit completed: {fit.slope_mv_per_dec:.2f} mV/dec."
            self.render_single()
            self.autosave()
            return self.snapshot()

    def _fit_params(self):
        window = parse_range_text(self.params.get("window_range", "12-15"), "window", integer=True, minimum=2)
        if window is None:
            window = (12, 15)
        return (
            int(window[0]),
            int(window[1]),
            _range_or_none(self.params.get("eta_range", ""), "eta"),
            _range_or_none(self.params.get("logj_range", ""), "logj"),
            float(self.params.get("min_r2", "0.95") or 0.95),
            _priority_key(self.params.get("fit_priority", "slope")),
            float(self.params.get("e_eq", "0") or 0.0),
        )

    def set_segment(self, index: int | None = None, selected: bool | None = None, color: str | None = None) -> dict:
        with self.lock:
            if index is not None:
                idx = int(index)
                self.state.segments.set_active(idx)
                if selected is not None:
                    self.state.segments.toggle(idx, bool(selected))
                if color:
                    self._app_state.setdefault("segment_colors", {})[idx] = str(color)
            self._store_current_file_ui_state()
            self.render_single()
            self.autosave()
            return self.snapshot()

    def select_all_segments(self, selected: bool) -> dict:
        with self.lock:
            if selected:
                self.state.segments.select_all_loaded()
            else:
                self.state.segments.clear_selection()
            self._store_current_file_ui_state()
            self.render_single()
            self.autosave()
            return self.snapshot()

    def add_comparison(self) -> dict:
        with self.lock:
            path = self.state.files.current_path
            if path is None:
                raise ValueError("No file is loaded.")
            checked = [int(i) for i in self._app_state.get("selected_segment_indices", [])]
            prepared_by = self._app_state.get("prepared_by_segment", {})
            fit_by = self._app_state.get("fit_by_segment", {})
            for seg_idx in checked:
                prepared = prepared_by.get(seg_idx)
                if prepared is None:
                    continue
                item_id = comparison_item_id(path, seg_idx)
                item = ComparisonItem(
                    item_id=item_id,
                    file_path=path,
                    file_name=self.state.files.display_name(path),
                    segment_index=seg_idx,
                    prepared=prepared,
                    fit=fit_by.get(seg_idx),
                    label=f"{self.state.files.display_name(path)}-Segment {seg_idx + 1}",
                    color=self._app_state.get("segment_colors", {}).get(seg_idx, COMPARISON_COLORS[seg_idx % len(COMPARISON_COLORS)]),
                    visible=True,
                )
                self.state.comparison.upsert(item)
            self._app_state["comparison_mode"] = True
            self.render_comparison()
            self.autosave()
            return self.snapshot()

    def update_comparison(self, data: dict) -> dict:
        with self.lock:
            item_id = str(data.get("item_id", ""))
            item = self.state.comparison.item_by_id(item_id)
            if item is not None:
                if "visible" in data:
                    item.visible = bool(data["visible"])
                if data.get("color"):
                    item.color = str(data["color"])
                if data.get("label") is not None:
                    item.set_label(str(data["label"]))
            if data.get("remove") and item is not None:
                self.state.comparison.remove(item_id)
            if data.get("clear"):
                self.state.comparison.clear()
            if data.get("comparison_lsv_style"):
                self._app_state["comparison_lsv_style"] = normalize_lsv_style(data.get("comparison_lsv_style"))
            if "comparison_tafel_fit_window" in data:
                self._app_state["comparison_tafel_fit_window"] = bool(data["comparison_tafel_fit_window"])
            self._app_state["comparison_mode"] = True
            self.render_comparison()
            self.autosave()
            return self.snapshot()

    def show_chart_mode(self, mode: str) -> dict:
        with self.lock:
            self._app_state["comparison_mode"] = mode == "comparison"
            if mode == "comparison":
                self.render_comparison()
            else:
                self.render_single()
            return self.snapshot()

    def _remember_current_result_cache(self) -> None:
        path = self.state.files.current_path
        if path is None or not self._app_state.get("prepared_by_segment"):
            return
        window_min, window_max, eta_range, logj_range, min_r2, fit_priority, e_eq = self._fit_params()
        pot, cur = self.formulas()
        selected = tuple(int(i) for i in self._app_state.get("selected_segment_indices", []))
        key = make_result_cache_key(
            tdms_path=path,
            potential_formula=pot,
            current_formula=cur,
            e_eq=e_eq,
            selected_segment_indices=selected,
            min_window=window_min,
            max_window=window_max,
            eta_range=eta_range,
            logj_range=logj_range,
            min_r2=min_r2,
            fit_priority=fit_priority,
        )
        self._remember_result_cache(key)

    def _remember_result_cache(self, cache_key: tuple) -> None:
        path = self.state.files.current_path
        if path is None:
            return
        active = int(self._app_state.get("active_segment_index", 0))
        prepared_by = dict(self._app_state.get("prepared_by_segment", {}))
        fit_by = dict(self._app_state.get("fit_by_segment", {}))
        self._app_state.setdefault("result_cache", {})[cache_key] = {
            "prepared": self._app_state.get("prepared") or prepared_by.get(active) or next(iter(prepared_by.values()), None),
            "fit": self._app_state.get("fit") or fit_by.get(active),
            "prepared_by_segment": prepared_by,
            "fit_by_segment": fit_by,
            "fit_error_by_segment": dict(self._app_state.get("fit_error_by_segment", {})),
            "manual_fit_regions": dict(self._app_state.get("manual_fit_regions", {})),
            "selected_segment_indices": list(self._app_state.get("selected_segment_indices", [])),
            "active_segment_index": active,
            "view_state": self._app_state.get("single_plot_view_state"),
            "limits": None,
        }
        self._app_state.setdefault("current_result_keys", {})[str(path)] = cache_key

    def _restore_result_cache_entry(self, cache_key, entry: dict) -> None:
        prepared_by = {int(k): v for k, v in entry.get("prepared_by_segment", {}).items()}
        fit_by = {int(k): v for k, v in entry.get("fit_by_segment", {}).items()}
        errors = {int(k): v for k, v in entry.get("fit_error_by_segment", {}).items()}
        self._app_state["prepared_by_segment"] = prepared_by
        self._app_state["fit_by_segment"] = fit_by
        self._app_state["fit_error_by_segment"] = errors
        self._app_state["manual_fit_regions"] = {int(k): v for k, v in entry.get("manual_fit_regions", {}).items()}
        self._app_state["selected_segment_indices"] = [int(i) for i in entry.get("selected_segment_indices", [])]
        active = int(entry.get("active_segment_index", 0))
        self._app_state["active_segment_index"] = active
        self._app_state["prepared"] = prepared_by.get(active) or next(iter(prepared_by.values()), None)
        self._app_state["fit"] = fit_by.get(active)
        path = self.state.files.current_path
        if path is not None:
            self._app_state.setdefault("current_result_keys", {})[str(path)] = cache_key

    def _store_current_file_ui_state(self) -> None:
        path = self.state.files.current_path
        if path is None:
            return
        entry = self._app_state.setdefault("file_ui_cache", {}).setdefault(str(path), {})
        pot, cur = self.formulas()
        entry["potential_formula"] = pot
        entry["current_formula"] = cur
        entry.update(self.params)
        entry["segment_colors"] = {str(k): v for k, v in self._app_state.get("segment_colors", {}).items()}
        entry["manual_fit_regions"] = {str(k): v for k, v in self._app_state.get("manual_fit_regions", {}).items()}
        entry["selected_segment_indices"] = list(self._app_state.get("selected_segment_indices", []))
        entry["active_segment_index"] = int(self._app_state.get("active_segment_index", 0))

    def _begin_new_project(self, title: str | None = None, cache_path: Path | None = None, entry_id: str | None = None) -> None:
        project_title = title or datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        project_id = entry_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        if cache_path is None:
            safe_title = re.sub(r'[<>:"/\\|?*]+', "-", project_title).strip() or project_id
            cache_path = HISTORY_CACHE_DIR / safe_title
        self._app_state["current_project_id"] = project_id
        self._app_state["current_project_title"] = project_title
        self._app_state["current_project_cache_path"] = str(cache_path)

    def autosave(self) -> None:
        selected_paths = [Path(path) for path in self._app_state.get("selected_paths", [])]
        if not selected_paths:
            return
        self._store_current_file_ui_state()
        self._remember_current_result_cache()
        if self._app_state.get("current_project_id") is None:
            self._begin_new_project()
        HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        title = str(self._app_state.get("current_project_title") or datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
        project_dir = Path(self._app_state.get("current_project_cache_path") or (HISTORY_CACHE_DIR / title))
        self._app_state["current_project_cache_path"] = str(project_dir)
        write_v3_project_dir(
            project_dir,
            build_v3_manifest(self),
            build_v3_file_ui(self),
            build_v3_result_index(self),
            build_v3_comparison(self),
            *build_v3_blobs(self),
            _hashes=self._current_project_hashes,
        )
        self._current_project_hashes = None
        entry = {
            "id": str(self._app_state.get("current_project_id")),
            "title": title,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cache_path": str(project_dir),
            "files": [str(path) for path in selected_paths],
        }
        history = [h for h in self._app_state.get("project_history", []) if h.get("id") != entry["id"]]
        self._app_state["project_history"] = [entry] + history[:79]
        try:
            save_app_settings(self)
        except Exception:
            pass

    def import_cache(self, cache_path: str) -> dict:
        with self.lock:
            path = Path(cache_path)
            if path.is_dir():
                payload = load_v3_project_dir(path)
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
            self._begin_new_project(title=path.stem, cache_path=path if path.is_dir() else None)
            selected_paths = [Path(p) for p in payload.get("selected_paths", [])]
            self._app_state["selected_paths"] = [p for p in selected_paths if p.exists()]
            self._app_state["file_ui_cache"] = dict(payload.get("file_ui_cache", {}))
            self._app_state["current_result_keys"] = {
                str(k): cache_key_from_json(v) for k, v in payload.get("current_result_keys", {}).items()
            }
            result_cache = {}
            for item in payload.get("result_cache", []):
                prepared_payloads = {
                    int(k): v for k, v in item.get("prepared_by_segment", {}).items()
                    if is_prepared_payload(v)
                }
                if not prepared_payloads and not is_prepared_payload(item.get("prepared")):
                    continue
                key = cache_key_from_json(item["key"])
                result_cache[key] = {
                    "prepared": prepared_from_dict(item["prepared"] if is_prepared_payload(item.get("prepared")) else next(iter(prepared_payloads.values()))),
                    "fit": fit_from_dict(item["fit"]) if item.get("fit") else None,
                    "prepared_by_segment": {k: prepared_from_dict(v) for k, v in prepared_payloads.items()},
                    "fit_by_segment": {int(k): fit_from_dict(v) for k, v in item.get("fit_by_segment", {}).items()},
                    "fit_error_by_segment": {int(k): v for k, v in item.get("fit_error_by_segment", {}).items()},
                    "manual_fit_regions": {int(k): v for k, v in item.get("manual_fit_regions", {}).items()},
                    "selected_segment_indices": item.get("selected_segment_indices", []),
                    "active_segment_index": int(item.get("active_segment_index", 0)),
                    "view_state": item.get("view_state"),
                    "limits": item.get("limits"),
                }
            self._app_state["result_cache"] = result_cache
            self._app_state["comparison_items"] = [
                ComparisonItem(
                    item_id=str(item["item_id"]),
                    file_path=Path(item["file_path"]),
                    file_name=str(item.get("file_name") or Path(item["file_path"]).stem),
                    segment_index=int(item["segment_index"]),
                    prepared=prepared_from_dict(item["prepared"]),
                    fit=fit_from_dict(item["fit"]) if item.get("fit") else None,
                    label=str(item.get("label") or ""),
                    color=str(item.get("color") or COMPARISON_COLORS[int(item["segment_index"]) % len(COMPARISON_COLORS)]),
                    visible=bool(item.get("visible", True)),
                )
                for item in payload.get("comparison_items", [])
                if is_prepared_payload(item.get("prepared"))
            ]
            current = Path(payload.get("current_path") or "") if payload.get("current_path") else None
            if current not in self._app_state["selected_paths"] and self._app_state["selected_paths"]:
                current = self._app_state["selected_paths"][0]
            if current is not None and current.exists():
                self._load_file(current)
            elif self._app_state["comparison_items"]:
                self._app_state["comparison_mode"] = True
                self.render_comparison()
            self._app_state["status"] = f"Imported cache {path.name}"
            self.autosave()
            return self.snapshot()

    def export_cache(self, target: str, v2: bool = False) -> dict:
        with self.lock:
            target_path = Path(target)
            self._store_current_file_ui_state()
            self._remember_current_result_cache()
            if v2:
                from core.cache import atomic_write_json

                atomic_write_json(target_path, build_cache_payload(self), indent=2)
            else:
                write_v3_project_dir(
                    target_path,
                    build_v3_manifest(self),
                    build_v3_file_ui(self),
                    build_v3_result_index(self),
                    build_v3_comparison(self),
                    *build_v3_blobs(self),
                )
            self._app_state["status"] = f"Exported cache to {target_path}"
            return self.snapshot()

    def export_current(self, kind: str, target: str) -> dict:
        with self.lock:
            prepared = self._app_state.get("prepared")
            fit = self._app_state.get("fit")
            channels = self._app_state.get("channels")
            target_path = Path(target)
            if kind == "raw_txt":
                export_txt(target_path, channels or {})
            elif kind == "processed_txt":
                if prepared is None or fit is None:
                    raise ValueError("No fitted active segment is available.")
                export_processed_txt(target_path, prepared, fit)
            elif kind == "npz":
                if prepared is None or fit is None:
                    raise ValueError("No fitted active segment is available.")
                export_fit_npz(target_path, prepared, fit)
            elif kind in {"png", "pdf", "svg"}:
                self._render_current_figure().savefig(target_path, dpi=180, bbox_inches="tight")
            else:
                raise ValueError(f"Unknown export kind: {kind}")
            self._app_state["status"] = f"Exported {target_path.name}"
            return self.snapshot()

    def render_single(self) -> None:
        self._app_state["comparison_mode"] = False
        fig = self._render_single_figure()
        self._current_png = self._figure_to_png(fig)
        plt.close(fig)

    def render_comparison(self) -> None:
        self._app_state["comparison_mode"] = True
        fig = self._render_comparison_figure()
        self._current_png = self._figure_to_png(fig)
        plt.close(fig)

    def _render_current_figure(self):
        return self._render_comparison_figure() if self._app_state.get("comparison_mode") else self._render_single_figure()

    def _render_single_figure(self):
        fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 5.4), dpi=150)
        fig.set_facecolor("#f8fafc")
        prepared_by = self._app_state.get("prepared_by_segment", {})
        fit_by = self._app_state.get("fit_by_segment", {})
        selected = sorted(int(i) for i in self._app_state.get("selected_segment_indices", []))
        active = int(self._app_state.get("active_segment_index", 0))
        colors = self._app_state.get("segment_colors", {})
        if not prepared_by:
            ax0.text(0.5, 0.5, "Load files and run fit", ha="center", va="center", transform=ax0.transAxes)
            ax1.text(0.5, 0.5, "Tafel", ha="center", va="center", transform=ax1.transAxes)
            return fig
        with matplotlib.rc_context(MPL_RC):
            ref = prepared_by.get(active) or next(iter(prepared_by.values()))
            for index in selected:
                prepared = prepared_by.get(index)
                if prepared is None:
                    continue
                color = colors.get(index, COMPARISON_COLORS[index % len(COMPARISON_COLORS)])
                lw = 2.2 if index == active else 1.2
                alpha = 1.0 if index == active else 0.45
                ax0.plot(prepared.e, prepared.j, marker="o", markersize=3, linewidth=lw, alpha=alpha, color=color, label=f"Segment {index + 1}")
                fit = fit_by.get(index)
                if fit is not None:
                    fit_indices = valid_fit_source_indices(fit, prepared)
                    if fit_indices.size:
                        ax0.scatter(prepared.e[fit_indices], prepared.j[fit_indices], s=24, color=color, edgecolors="#111827", linewidths=0.5)
                    x, y, mask, _source = clean_fit_plot_data(fit)
                    ax1.scatter(x[~mask], y[~mask], s=13, color=color, alpha=0.25)
                    ax1.scatter(x[mask], y[mask], s=26, color=color, edgecolors="#111827", linewidths=0.5, label=f"Segment {index + 1} ({fit.slope_mv_per_dec:.1f} mV/dec)")
                    xs = x[mask]
                    if xs.size >= 2:
                        x_line = np.linspace(float(xs.min()), float(xs.max()), 100)
                        ax1.plot(x_line, fit.slope_v_per_dec * x_line + fit.intercept_v, color=color, linestyle="--", linewidth=1.8)
                else:
                    x_pts, y_pts = compute_tafel_points(prepared)
                    ax1.scatter(x_pts, y_pts, s=13, color=color, alpha=alpha, label=f"Segment {index + 1}")
            ax0.set_xlabel(ref.e_label)
            ax0.set_ylabel(ref.j_label)
            ax0.set_title("Electrochemical data")
            ax1.set_xlabel("log10(|j|)")
            ax1.set_ylabel(ref.tafel_y_label)
            active_fit = fit_by.get(active)
            ax1.set_title(f"Tafel fit: {active_fit.slope_mv_per_dec:.2f} mV/dec, R2={active_fit.r2:.4f}" if active_fit else "Tafel fit")
            ax0.grid(True, alpha=0.25)
            ax1.grid(True, alpha=0.25)
            ax0.legend(fontsize=8)
            ax1.legend(fontsize=8)
            fig.tight_layout()
        return fig

    def _render_comparison_figure(self):
        fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 5.4), dpi=150)
        fig.set_facecolor("#f8fafc")
        visible = [item for item in self._app_state.get("comparison_items", []) if item.visible]
        if not visible:
            ax0.text(0.5, 0.5, "No comparison items", ha="center", va="center", transform=ax0.transAxes)
            ax1.text(0.5, 0.5, "Tafel comparison", ha="center", va="center", transform=ax1.transAxes)
            return fig
        with matplotlib.rc_context(MPL_RC):
            lsv_style = normalize_lsv_style(self._app_state.get("comparison_lsv_style"))
            fit_window = bool(self._app_state.get("comparison_tafel_fit_window", False))
            for item in visible:
                prepared = item.prepared
                fit = item.fit
                label = item.display_label
                kwargs = {"marker": "o", "linestyle": "-", "markersize": 3, "linewidth": 1.4}
                if lsv_style == "line":
                    kwargs = {"marker": None, "linestyle": "-", "markersize": 0, "linewidth": 1.4}
                elif lsv_style == "scatter":
                    kwargs = {"marker": "o", "linestyle": "None", "markersize": 3, "linewidth": 0}
                ax0.plot(prepared.e, prepared.j, color=item.color, label=label, **kwargs)
                if fit is not None:
                    x, y, mask, source = clean_fit_plot_data(fit)
                    display = tafel_window_mask(mask, fit_window, source)
                    ax1.scatter(x[display & ~mask], y[display & ~mask], s=13, color=item.color, alpha=0.22)
                    ax1.scatter(x[display & mask], y[display & mask], s=26, color=item.color, edgecolors="#111827", linewidths=0.5, label=f"{label} ({fit.slope_mv_per_dec:.1f})")
                    xs = x[display & mask]
                    if xs.size >= 2:
                        line_x = np.linspace(float(xs.min()), float(xs.max()), 100)
                        ax1.plot(line_x, fit.slope_v_per_dec * line_x + fit.intercept_v, color=item.color, linestyle="--", linewidth=1.8)
            ref = visible[0].prepared
            ax0.set_xlabel(ref.e_label)
            ax0.set_ylabel(ref.j_label)
            ax0.set_title("Data comparison")
            ax1.set_xlabel("log10(|j|)")
            ax1.set_ylabel(ref.tafel_y_label)
            ax1.set_title("Tafel slope comparison")
            ax0.grid(True, alpha=0.25)
            ax1.grid(True, alpha=0.25)
            ax0.legend(fontsize=8)
            ax1.legend(fontsize=8)
            fig.tight_layout()
        return fig

    def _figure_to_png(self, fig) -> str:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


SERVICE = WebBackend()


class Handler(BaseHTTPRequestHandler):
    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(_json_safe(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(200, {"ok": True})

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/state":
                self._send(200, {"ok": True, "state": SERVICE.snapshot()})
            elif path == "/api/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"ok": False, "error": "Not found"})
        except Exception as exc:
            self._send(500, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            data = self._read_json()
            routes = {
                "/api/load-files": lambda: SERVICE.load_files(data.get("paths", [])),
                "/api/select-file": lambda: SERVICE.select_file(data["path"]),
                "/api/remove-file": lambda: SERVICE.remove_file(data["path"]),
                "/api/set-formulas": lambda: SERVICE.set_formulas(data.get("potential", ""), data.get("current", "")),
                "/api/set-params": lambda: SERVICE.set_params(data),
                "/api/fit": lambda: SERVICE.run_fit(force=bool(data.get("force", False))),
                "/api/manual-fit": lambda: SERVICE.manual_fit(data),
                "/api/set-segment": lambda: SERVICE.set_segment(data.get("index"), data.get("selected"), data.get("color")),
                "/api/select-all-segments": lambda: SERVICE.select_all_segments(bool(data.get("selected", True))),
                "/api/add-comparison": lambda: SERVICE.add_comparison(),
                "/api/update-comparison": lambda: SERVICE.update_comparison(data),
                "/api/chart-mode": lambda: SERVICE.show_chart_mode(str(data.get("mode", "single"))),
                "/api/cache/import": lambda: SERVICE.import_cache(data["path"]),
                "/api/cache/export": lambda: SERVICE.export_cache(data["path"], bool(data.get("v2", False))),
                "/api/export/current": lambda: SERVICE.export_current(data["kind"], data["path"]),
            }
            if path not in routes:
                self._send(404, {"ok": False, "error": "Not found"})
                return
            self._send(200, {"ok": True, "state": routes[path]()})
        except Exception as exc:
            self._send(400, {"ok": False, "error": str(exc), "state": SERVICE.snapshot()})

    def log_message(self, _format: str, *args) -> None:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    host, port = server.server_address
    print(json.dumps({"event": "TAFEL_WEB_BACKEND", "host": host, "port": port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
