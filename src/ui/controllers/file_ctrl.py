from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, cast
from datetime import datetime

from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import POTENTIAL_PREFERRED_NAMES, CURRENT_PREFERRED_NAMES, COMPARISON_COLORS
from core.utils import parse_range_text, pick_channel_name, priority_label_to_key
from ui.color_utils import interpolate_hex
from ui.controllers.base import BaseAppController
from ui.controllers.worker_utils import stop_worker

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


def _map_palette_colors(palette_colors: list[str], target_count: int, mode: str) -> list[str]:
    if target_count <= 0 or not palette_colors:
        return []
    if mode != "interpolate":
        return [palette_colors[i % len(palette_colors)] for i in range(target_count)]

    source_count = len(palette_colors)
    if source_count == 1:
        return [palette_colors[0] for _ in range(target_count)]
    if source_count == target_count:
        return list(palette_colors)
    if source_count > target_count:
        if target_count == 1:
            return [palette_colors[0]]
        return [
            palette_colors[round(i * (source_count - 1) / (target_count - 1))]
            for i in range(target_count)
        ]

    anchors = [
        min(target_count - 1, int(i * (target_count - 1) / source_count))
        for i in range(source_count)
    ]
    result: list[str] = []
    for target_index in range(target_count):
        if target_index <= anchors[0]:
            result.append(palette_colors[0])
            continue
        if target_index >= anchors[-1]:
            result.append(palette_colors[-1])
            continue
        for left_index in range(source_count - 1):
            left_pos = anchors[left_index]
            right_pos = anchors[left_index + 1]
            if left_pos <= target_index <= right_pos:
                span = max(1, right_pos - left_pos)
                t = (target_index - left_pos) / span
                result.append(interpolate_hex(palette_colors[left_index], palette_colors[left_index + 1], t))
                break
    return result


def _path_key(path: Path | str) -> str:
    return str(Path(path))


def _remove_cache_path(cache_path: Path) -> None:
    """Remove a cache entry (v2 JSON file or v3 directory)."""
    import shutil
    try:
        if cache_path.is_dir():
            shutil.rmtree(cache_path, ignore_errors=True)
        else:
            cache_path.unlink(missing_ok=True)
    except Exception:
        pass


def _file_data_cache_key(path: Path) -> tuple | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    try:
        resolved = str(path.resolve(strict=False)).lower()
    except OSError:
        resolved = str(path).lower()
    return (
        "file-data-v1",
        resolved,
        int(stat.st_size),
        int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
        int(getattr(stat, "st_ctime_ns", int(stat.st_ctime * 1_000_000_000))),
    )


def _resolve_formulas_for_channels(
    channels: dict,
    potential_formula: str,
    current_formula: str,
) -> tuple[str, str, list[str]]:
    warnings: list[str] = []

    def try_or_default(text: str, preferred: list[str]) -> str:
        raw = text.strip()
        if raw:
            try:
                normalize_formula(channels, raw, preferred)
                return raw
            except Exception as exc:
                warnings.append(str(exc))
        try:
            return f"[{pick_channel_name(channels, preferred)}]"
        except Exception as exc:
            warnings.append(str(exc))
            return ""

    return (
        try_or_default(potential_formula, POTENTIAL_PREFERRED_NAMES),
        try_or_default(current_formula, CURRENT_PREFERRED_NAMES),
        warnings,
    )


def _with_cache_key_path(cache_key: tuple, new_path: Path) -> tuple:
    if not cache_key:
        return cache_key
    if not isinstance(cache_key[0], str):
        return cache_key
    return (str(new_path), *cache_key[1:])


def _normalize_manual_regions(raw: dict | None) -> dict[int, dict[str, float]]:
    regions: dict[int, dict[str, float]] = {}
    if not isinstance(raw, dict):
        return regions
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            index = int(key)
            x_min = float(value["x_min"])
            x_max = float(value["x_max"])
            y_min = float(value["y_min"])
            y_max = float(value["y_max"])
        except (KeyError, TypeError, ValueError):
            continue
        regions[index] = {
            "x_min": min(x_min, x_max),
            "x_max": max(x_min, x_max),
            "y_min": min(y_min, y_max),
            "y_max": max(y_min, y_max),
        }
    return regions


def _common_tail_score(left: Path, right: Path) -> int:
    left_parts = [part.lower() for part in left.parts]
    right_parts = [part.lower() for part in right.parts]
    score = 0
    for a, b in zip(reversed(left_parts), reversed(right_parts)):
        if a != b:
            break
        score += 1
    return score


def _same_file_candidate(old_path: Path) -> Path | None:
    if old_path.exists():
        return old_path
    parts = old_path.parts
    if len(parts) > 1:
        onedrive_same_drive = Path(old_path.anchor) / "OneDrive" / Path(*parts[1:])
        if onedrive_same_drive.exists():
            return onedrive_same_drive
    home_onedrive = Path.home() / "OneDrive" / Path(*parts[1:]) if len(parts) > 1 else None
    if home_onedrive is not None and home_onedrive.exists():
        return home_onedrive
    return None


class CacheWriteWorker(QThread):
    """Background worker for JSON serialization and disk I/O."""

    finished = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode: str = "idle"  # idle | single | v3
        self._payload: dict | None = None
        self._path: Path | None = None
        self._v3_args: dict | None = None
        self._queued_mode: str | None = None
        self._queued_payload: dict | None = None
        self._queued_path: Path | None = None
        self._queued_v3_args: dict | None = None
        self._lock = Lock()

    def request_write(self, payload: dict, path: Path) -> None:
        """Write a single JSON file (v2 format)."""
        should_start = False
        with self._lock:
            if self.isRunning():
                self._queued_mode = "single"
                self._queued_payload = payload
                self._queued_path = path
                self._queued_v3_args = None
                return
            self._payload = payload
            self._path = path
            self._v3_args = None
            self._mode = "single"
            should_start = True
        if should_start:
            self.start()

    def request_v3_write(self, project_dir: Path, manifest: dict, file_ui: dict,
                         result_index: dict, comparison: list[dict],
                         prepared_blobs: dict[str, dict],
                         fit_blobs: dict[str, dict],
                         hashes: dict | None = None) -> None:
        """Write a v3 directory structure."""
        args = {
            "project_dir": project_dir,
            "manifest": manifest,
            "file_ui": file_ui,
            "result_index": result_index,
            "comparison": comparison,
            "prepared_blobs": prepared_blobs,
            "fit_blobs": fit_blobs,
            "hashes": hashes or {},
        }
        should_start = False
        with self._lock:
            if self.isRunning():
                self._queued_mode = "v3"
                self._queued_payload = None
                self._queued_path = None
                self._queued_v3_args = args
                return
            self._payload = None
            self._path = None
            self._v3_args = args
            self._mode = "v3"
            should_start = True
        if should_start:
            self.start()

    def run(self) -> None:
        try:
            while True:
                with self._lock:
                    mode = self._mode
                    payload = dict(self._payload) if isinstance(self._payload, dict) else None
                    path = Path(self._path) if self._path is not None else None
                    v3_args = dict(self._v3_args) if isinstance(self._v3_args, dict) else None
                if mode == "v3" and v3_args:
                    from core.cache import write_v3_project_dir
                    new_hashes = write_v3_project_dir(
                        v3_args["project_dir"], v3_args["manifest"], v3_args["file_ui"],
                        v3_args["result_index"], v3_args["comparison"],
                        v3_args["prepared_blobs"], v3_args["fit_blobs"],
                        _hashes=v3_args["hashes"],
                    )
                    self._result_hashes = new_hashes
                elif mode == "single" and payload and path:
                    from core.cache import atomic_write_json
                    atomic_write_json(path, payload)
                else:
                    break
                with self._lock:
                    if self._queued_mode is None:
                        self._payload = None
                        self._path = None
                        self._v3_args = None
                        self._mode = "idle"
                        break
                    self._mode = self._queued_mode
                    self._payload = self._queued_payload
                    self._path = self._queued_path
                    self._v3_args = self._queued_v3_args
                    self._queued_mode = None
                    self._queued_payload = None
                    self._queued_path = None
                    self._queued_v3_args = None
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class FileLoadWorker(QThread):
    """Background worker for loading file data."""

    finished = Signal(object, object, object, object, object)  # channels, potential_f, current_f, segments, warnings
    error = Signal(str)

    def __init__(self, file_path: Path, potential_formula: str, current_formula: str):
        super().__init__()
        self.file_path = file_path
        self.potential_formula = potential_formula
        self.current_formula = current_formula
        self.generation: int | None = None

    def run(self):
        file_path = self.file_path
        try:
            channels = read_data_all_channels(file_path)
            pot_f, cur_f, warnings = self._resolve_formulas(channels)
            segments = []
            if pot_f:
                try:
                    segments = build_segment_infos(channels, pot_f)
                except Exception as exc:
                    warnings.append(str(exc))
            self.finished.emit(channels, pot_f, cur_f, segments, warnings)
        except Exception as exc:
            self.error.emit(str(exc))

    def _resolve_formulas(self, channels: dict) -> tuple[str, str, list[str]]:
        return _resolve_formulas_for_channels(
            channels,
            self.potential_formula,
            self.current_formula,
        )


class FileController(BaseAppController):
    """Manages file loading, switching, removal, palette, and segment interaction."""

    file_loaded = Signal()
    file_load_failed = Signal(str)

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FileLoadWorker | None = None
        self._cache_writer = CacheWriteWorker(app)
        self._cache_writer.finished.connect(self._on_cache_write_finished)
        self._cache_writer.error.connect(
            lambda msg: app.status_bar.setText(f"历史项目自动保存失败: {msg[:80]}")
        )
        self._pending_history_entry: dict | None = None
        self._autosave_timer = QTimer(app)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(800)
        self._autosave_timer.timeout.connect(self.autosave_project_history)
        if hasattr(app, "views"):
            app.views.refresh_palette_controls()

    # ━━ File operations ━━

    def on_files_loaded(self, paths: list[Path]) -> None:
        app = self.app
        if paths and not app.state.files.selected_paths:
            self._begin_new_project()
        app.state.files.merge_paths(paths)
        app.views.refresh_file_list()
        if paths:
            self._load_file(paths[0])

    def on_file_selected(self, path: Path) -> None:
        self.app.file_segment_panel.set_current_file(path)
        self._load_file(path)

    def _cached_file_load(
        self,
        path: Path,
        potential_formula: str,
        current_formula: str,
    ) -> tuple[dict, str, str, list, list[str]] | None:
        cache_key = _file_data_cache_key(path)
        if cache_key is None:
            return None
        entry = self.app._app_state.setdefault("file_data_cache", {}).get(cache_key)
        if not isinstance(entry, dict):
            return None
        channels = entry.get("channels")
        if not isinstance(channels, dict):
            return None
        pot_f, cur_f, warnings = _resolve_formulas_for_channels(channels, potential_formula, current_formula)
        segments_by_formula = entry.setdefault("segments_by_formula", {})
        segments = segments_by_formula.get(pot_f) if pot_f else []
        if segments is None and pot_f:
            try:
                segments = build_segment_infos(channels, pot_f)
                segments_by_formula[pot_f] = segments
            except Exception as exc:
                warnings.append(str(exc))
                segments = []
        return channels, pot_f, cur_f, segments or [], warnings

    def _remember_file_load(
        self,
        path: Path,
        channels: dict,
        potential_formula: str,
        segments: list,
    ) -> None:
        cache_key = _file_data_cache_key(path)
        if cache_key is None:
            return
        cache = self.app._app_state.setdefault("file_data_cache", {})
        entry = cache.setdefault(cache_key, {"channels": channels, "segments_by_formula": {}})
        entry["channels"] = channels
        entry.setdefault("segments_by_formula", {})[potential_formula] = segments
        if len(cache) > 16:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)

    def _cached_result_for_path(self, path: Path) -> dict | None:
        app = self.app
        cache_key = app._app_state.get("current_result_keys", {}).get(str(path))
        if cache_key is None:
            return None
        entry = app._app_state.get("result_cache", {}).get(cache_key)
        return entry if isinstance(entry, dict) else None

    def result_cache_entry(self, cache_key: tuple) -> dict | None:
        entry = self.app._app_state.get("result_cache", {}).get(cache_key)
        return entry if isinstance(entry, dict) else None

    def restore_result_cache_entry(self, cache_key: tuple, entry: dict, *, status: str = "") -> bool:
        app = self.app
        selected = [int(index) for index in entry.get("selected_segment_indices", app._app_state.get("selected_segment_indices", []))]
        prepared_by_segment = {
            int(index): value
            for index, value in entry.get("prepared_by_segment", {}).items()
        }
        fit_by_segment = {
            int(index): value
            for index, value in entry.get("fit_by_segment", {}).items()
        }
        fit_error_by_segment = {
            int(index): value
            for index, value in entry.get("fit_error_by_segment", {}).items()
        }
        covered = set(prepared_by_segment) | set(fit_error_by_segment)
        if selected and not set(int(index) for index in selected).issubset(covered):
            return False

        active_index = int(app._app_state.get("active_segment_index", entry.get("active_segment_index", 0)))
        if active_index not in prepared_by_segment and prepared_by_segment:
            active_index = next(iter(prepared_by_segment))
        app._app_state["prepared_by_segment"] = prepared_by_segment
        app._app_state["fit_by_segment"] = fit_by_segment
        app._app_state["fit_error_by_segment"] = fit_error_by_segment
        app._app_state["manual_fit_regions"] = _normalize_manual_regions(entry.get("manual_fit_regions", {}))
        app._app_state["selected_segment_indices"] = [int(index) for index in selected]
        app._app_state["active_segment_index"] = active_index
        app._app_state["prepared"] = prepared_by_segment.get(active_index) or next(iter(prepared_by_segment.values()), None)
        app._app_state["fit"] = fit_by_segment.get(active_index)
        app._app_state["single_plot_view_state"] = entry.get("view_state") or app._app_state.get("single_plot_view_state")
        path = app.state.files.current_path
        if path is not None:
            app._app_state.setdefault("current_result_keys", {})[str(path)] = cache_key
        app.views.refresh_segments()
        if app._app_state.get("prepared") is not None:
            app.views.render_single()
        if status:
            app.status_bar.setText(status)
        return True

    def _restore_cached_single_view_state(self, path: Path) -> None:
        entry = self._cached_result_for_path(path)
        if entry is None:
            return
        view_state = entry.get("view_state")
        if view_state is None and entry.get("limits"):
            from core.rendering import view_state_from_legacy_limits

            view_state = view_state_from_legacy_limits(entry.get("limits"))
        if view_state is not None:
            self.app._app_state["single_plot_view_state"] = view_state

    def on_file_renamed(self, path: Path, new_name: str) -> None:
        app = self.app
        app.state.files.set_alias(path, new_name)
        app.state.comparison.sync_file_alias(path, app.state.files.display_name(path))
        app.views.refresh_file_list()
        app.comparison.refresh_list()
        self.schedule_project_autosave()

    def _load_file(self, path: Path) -> None:
        app = self.app
        generation = app.state.operations.bump_generation()
        if app._app_state.get("manual_mode") and hasattr(app, "fitting"):
            app.fitting.disable_manual_mode()
        else:
            from core.rendering import destroy_selector
            destroy_selector(app)
        if hasattr(app, "fitting"):
            app.fitting.cancel_running()
        app.state.analysis.begin_file_load(path)
        self._restore_cached_single_view_state(path)
        app.file_segment_panel.set_segments([], 0, set(), {}, {})
        app.chart.clear_figure()
        # Clean up previous worker
        stop_worker(self._worker)
        self._worker = None
        app.status_bar.setText(f"正在加载 {path.name} …")
        entry = app._app_state.setdefault("file_ui_cache", {}).get(str(path), {})
        current_formulas = app.toolbar.get_formulas()
        formulas = (
            str(entry.get("potential_formula") or current_formulas[0]),
            str(entry.get("current_formula") or current_formulas[1]),
        )
        cached = self._cached_file_load(path, formulas[0], formulas[1])
        if cached is not None:
            channels, pot_f, cur_f, segments, warnings = cached
            app.status_bar.setText(f"已从内存缓存加载 {path.name}")
            self._on_load_finished(channels, pot_f, cur_f, segments, warnings, path, generation)
            return
        self._worker = FileLoadWorker(path, formulas[0], formulas[1])
        self._worker.generation = generation
        self._worker.finished.connect(self._on_load_finished_from_worker)
        self._worker.error.connect(self._on_load_error_from_worker)
        self._worker.start()

    def _on_load_finished_from_worker(self, channels, pot_f, cur_f, segments, warnings) -> None:
        worker = cast(FileLoadWorker | None, self.sender())
        if worker is None:
            return
        self._on_load_finished(channels, pot_f, cur_f, segments, warnings, worker.file_path, worker.generation)

    def _on_load_error_from_worker(self, msg) -> None:
        worker = cast(FileLoadWorker | None, self.sender())
        if worker is None:
            return
        self._on_load_error(msg, worker.file_path, worker.generation)

    def _on_load_finished(
        self,
        channels,
        pot_f,
        cur_f,
        segments,
        formula_warnings=None,
        expected_path=None,
        generation: int | None = None,
    ) -> None:
        app = self.app
        if expected_path is not None and app._app_state.get("tdms_path") != expected_path:
            return
        if not app.state.operations.is_current(generation):
            return
        if expected_path is not None:
            self._remember_file_load(Path(expected_path), channels, pot_f, segments)
        if hasattr(app.toolbar, "set_available_channels"):
            app.toolbar.set_available_channels(list(channels.keys()))
        scheme_name = app.state.palette.active_name
        segment_colors = {}
        for s in segments:
            idx = s.index
            color = app.state.palette.color_at(idx, scheme_name)
            if color:
                segment_colors[idx] = color
        path = app._app_state["tdms_path"]
        cached_entry = app._app_state.setdefault("file_ui_cache", {}).get(str(path), {})
        cached_colors = cached_entry.get("segment_colors")
        if isinstance(cached_colors, dict):
            for key, value in cached_colors.items():
                try:
                    segment_colors[int(key)] = str(value)
                except (TypeError, ValueError):
                    continue
        app._app_state["_precomputed_segments"] = segments
        app.state.analysis.apply_loaded_file(
            channels=channels,
            segment_infos=segments,
            segment_colors=segment_colors,
        )
        if isinstance(cached_entry.get("selected_segment_indices"), list):
            app._app_state["selected_segment_indices"] = [
                int(index) for index in cached_entry.get("selected_segment_indices", [])
            ]
        if cached_entry.get("active_segment_index") is not None:
            try:
                app._app_state["active_segment_index"] = int(cached_entry.get("active_segment_index"))
            except (TypeError, ValueError):
                pass
        app._app_state["manual_fit_regions"] = _normalize_manual_regions(
            cached_entry.get("manual_fit_regions", {})
        )

        app._app_state["_suppress_toolbar_autosave"] = True
        try:
            # Update toolbar formulas
            app.toolbar.set_formulas(pot_f, cur_f)

            # Update toolbar params
            cached_params = {
                key: cached_entry[key]
                for key in ("e_eq", "window_range", "eta_range", "logj_range", "min_r2", "fit_priority")
                if key in cached_entry
            }
            if not cached_params:
                cached_params = dict(app._app_state.get("saved_parameter_defaults") or {})
            if cached_params:
                app.toolbar.set_params(cached_params)
        finally:
            app._app_state.pop("_suppress_toolbar_autosave", None)

        # Update segment panel
        app.views.refresh_segments(rebuild=True)

        # Update status
        app.file_segment_panel.set_current_file(path)
        app.file_segment_panel.set_processed(path)
        if app._app_state.get("current_project_id") is None:
            self._begin_new_project()
        if app._app_state.pop("_suppress_next_load_autosave", False):
            app.views.refresh_history_panel()
        if not pot_f or not cur_f:
            app.status_bar.setText(
                f"已加载 {path.name}，检测到 {len(channels)} 个通道；请选择电位/电流通道后点击拟合"
            )
        else:
            app.status_bar.setText(f"已加载 {path.name}")

        # Clear chart
        app.chart.clear_figure()
        self.file_loaded.emit()
        if pot_f and cur_f and segments:
            app.fitting.run_fit()
        if hasattr(app, "history_workspace"):
            app.history_workspace.set_busy(False)

    def _on_load_error(self, msg: str, expected_path=None, generation: int | None = None) -> None:
        if expected_path is not None and self.app._app_state.get("tdms_path") != expected_path:
            return
        if not self.app.state.operations.is_current(generation):
            return
        if hasattr(self.app, "history_workspace"):
            self.app.history_workspace.set_busy(False)
        self.app.status_bar.setText("加载失败")
        QMessageBox.critical(self.app, "加载失败", msg)

    # ━━ File removal ━━

    def on_file_removed(self, path: Path) -> None:
        app = self.app
        try:
            from core.cache import file_fingerprint
            removed_fingerprint = file_fingerprint(path)
            app._app_state["result_cache"] = {
                cache_key: cached
                for cache_key, cached in app._app_state.get("result_cache", {}).items()
                if not cache_key or cache_key[0] != removed_fingerprint
            }
        except Exception:
            pass
        app.state.files.remove_path(path)
        app.state.comparison.remove_file_items(path)
        app.views.refresh_file_list()
        app.comparison.refresh_list()
        # Switch to next file or clear
        remaining = app.state.files.selected_paths
        if remaining:
            app.state.files.set_current_path(remaining[0])
            self._load_file(remaining[0])
            self.schedule_project_autosave()
        else:
            app.state.reset_current_file()
            app._app_state["current_project_id"] = None
            app._app_state["current_project_title"] = None
            app._app_state["current_project_cache_path"] = None
            app.views.refresh_segments(rebuild=True)
            app.views.render_active_chart()
            app.status_bar.setText("等待选择数据文件")

    # ━━ Segment interaction ━━

    def on_segment_activated(self, index: int) -> None:
        app = self.app
        app.state.segments.set_active(index)
        app.views.refresh_segments()
        self._rerender_current()

    def on_segment_toggled(self, index: int, checked: bool) -> None:
        app = self.app
        app.state.segments.toggle(index, checked)
        app.views.refresh_segments()
        if checked:
            existing_fit = app._app_state.get("fit_by_segment", {}).get(index)
            if existing_fit is not None:
                self._rerender_current()
                self.schedule_project_autosave()
            else:
                app.fitting.run_fit()
        else:
            self._rerender_current()
            self.schedule_project_autosave()

    def on_segment_color(self, index: int, _dummy: str = "") -> None:
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        current = self.app._app_state.get("segment_colors", {}).get(index, COMPARISON_COLORS[index % len(COMPARISON_COLORS)])
        color = QColorDialog.getColor(QColor(current), self.app)
        if color.isValid():
            app = self.app
            app._app_state["segment_colors"][index] = color.name()
            self._refresh_segment_panel()
            self._rerender_current()
            self.schedule_project_autosave()

    def on_select_all(self) -> None:
        app = self.app
        app.state.segments.select_all_loaded()
        app.views.refresh_segments()
        self.schedule_project_autosave()
        app.fitting.run_fit()

    def on_clear_all(self) -> None:
        app = self.app
        app.state.segments.clear_selection()
        app.views.refresh_segments()
        from core.rendering import draw_placeholder
        draw_placeholder(app)
        self.schedule_project_autosave()

    # ━━ Cache import ━━

    def _project_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    def _begin_new_project(self, *, title: str | None = None, cache_path: Path | None = None, entry_id: str | None = None) -> None:
        app = self.app
        project_title = title or self._project_timestamp()
        project_id = entry_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        if cache_path is None:
            from ui.settings import HISTORY_CACHE_DIR
            safe_title = re.sub(r'[<>:"/\\|?*]+', "-", project_title).strip() or project_id
            cache_path = HISTORY_CACHE_DIR / safe_title
        app._app_state["current_project_id"] = project_id
        app._app_state["current_project_title"] = project_title
        app._app_state["current_project_cache_path"] = str(cache_path)
        app._app_state.pop("_last_cache_payload_hash", None)

    def _adopt_history_project_for_cache(self, cache_path: Path) -> bool:
        target = str(Path(cache_path))
        for entry in self.app._app_state.get("project_history", []):
            if str(Path(entry.get("cache_path", ""))) != target:
                continue
            self._begin_new_project(
                title=str(entry.get("title") or self._project_timestamp()),
                cache_path=Path(target),
                entry_id=str(entry.get("id") or target),
            )
            return True
        return False

    def _cache_current_analysis_state(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        self._store_current_file_ui_state()
        prepared_by_segment = {
            int(index): value
            for index, value in app._app_state.get("prepared_by_segment", {}).items()
        }
        if path is None or not prepared_by_segment:
            return
        from core.cache import make_result_cache_key
        from core.rendering import (
            axes_limits_from_view_state,
            capture_plot_view_state,
            persist_current_plot_view_state,
        )

        params = app.toolbar.get_params()
        try:
            window_range = parse_range_text(
                params.get("window_range", "") or "12-15",
                "窗口点数范围",
                integer=True,
                minimum=2,
            )
            if window_range is None:
                raise ValueError("窗口点数范围不能为空")
            window_min, window_max = int(window_range[0]), int(window_range[1])
        except ValueError:
            window_min, window_max = 12, 15
        try:
            min_r2 = float(params.get("min_r2", "") or "0.95")
        except ValueError:
            min_r2 = 0.95
        try:
            eta_range = parse_range_text(params.get("eta_range", ""), "η 范围", allow_empty=True)
        except ValueError:
            eta_range = None
        try:
            logj_range = parse_range_text(params.get("logj_range", ""), "log(j) 范围", allow_empty=True)
        except ValueError:
            logj_range = None
        fit_priority = priority_label_to_key(params.get("fit_priority", "斜率更低优先"))
        try:
            e_eq = float(params.get("e_eq", "") or 0.0)
        except ValueError:
            e_eq = 0.0
        pot_f, cur_f = app.toolbar.get_formulas()
        selected = tuple(int(index) for index in app._app_state.get("selected_segment_indices", []))
        cache_key = make_result_cache_key(
            tdms_path=Path(path),
            potential_formula=pot_f,
            current_formula=cur_f,
            e_eq=e_eq,
            selected_segment_indices=selected,
            min_window=window_min,
            max_window=window_max,
            eta_range=eta_range,
            logj_range=logj_range,
            min_r2=min_r2,
            fit_priority=fit_priority,
        )
        active_index = int(app._app_state.get("active_segment_index", 0))
        prepared = app._app_state.get("prepared") or prepared_by_segment.get(active_index)
        if prepared is None and prepared_by_segment:
            prepared = next(iter(prepared_by_segment.values()))
        persist_current_plot_view_state(app)
        if app._app_state.get("active_chart_mode") == "single":
            view_state = capture_plot_view_state(app)
        else:
            view_state = app._app_state.get("single_plot_view_state")
        app._app_state.setdefault("result_cache", {})[cache_key] = {
            "prepared": prepared,
            "fit": app._app_state.get("fit"),
            "prepared_by_segment": prepared_by_segment,
            "fit_by_segment": dict(app._app_state.get("fit_by_segment", {})),
            "fit_error_by_segment": dict(app._app_state.get("fit_error_by_segment", {})),
            "manual_fit_regions": dict(app._app_state.get("manual_fit_regions", {})),
            "selected_segment_indices": list(selected),
            "active_segment_index": active_index,
            "view_state": view_state,
            "limits": axes_limits_from_view_state(view_state),
        }
        app._app_state.setdefault("current_result_keys", {})[str(path)] = cache_key

    def _store_current_file_ui_state(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if path is None:
            return
        entry = app._app_state.setdefault("file_ui_cache", {}).setdefault(str(path), {})
        pot_f, cur_f = app.toolbar.get_formulas()
        entry["potential_formula"] = pot_f
        entry["current_formula"] = cur_f
        entry.update(app.toolbar.get_params())
        entry["segment_colors"] = {
            str(index): color
            for index, color in app._app_state.get("segment_colors", {}).items()
        }
        entry["manual_fit_regions"] = {
            str(index): region
            for index, region in app._app_state.get("manual_fit_regions", {}).items()
            if isinstance(region, dict)
        }
        entry["selected_segment_indices"] = list(app._app_state.get("selected_segment_indices", []))
        entry["active_segment_index"] = int(app._app_state.get("active_segment_index", 0))

    def autosave_project_history(self) -> None:
        app = self.app
        selected_paths = [Path(path) for path in app._app_state.get("selected_paths", [])]
        if not selected_paths:
            return
        try:
            self._cache_current_analysis_state()
            if app._app_state.get("current_project_id") is None:
                self._begin_new_project()
            from core.cache import (
                build_v3_manifest, build_v3_file_ui, build_v3_result_index,
                build_v3_comparison, build_v3_blobs, payload_hash,
            )
            from ui.settings import HISTORY_CACHE_DIR
            HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            project_id = str(app._app_state.get("current_project_id"))
            title = str(app._app_state.get("current_project_title") or self._project_timestamp())
            safe_title = re.sub(r'[<>:"/\\|?*]+', "-", title).strip() or project_id
            project_dir = HISTORY_CACHE_DIR / safe_title
            # Detect v2→v3 migration: old path was a .json file
            old_path = app._app_state.get("current_project_cache_path", "")
            if old_path and old_path.endswith(".json") and Path(old_path).is_file():
                app._app_state["_old_v2_cache_path"] = old_path
            app._app_state["current_project_cache_path"] = str(project_dir)

            # Build all v3 components on main thread (fast dict construction)
            manifest = build_v3_manifest(app)
            manifest_hash = payload_hash(manifest)
            if manifest_hash == app._app_state.get("_last_manifest_hash"):
                # Check if other components changed
                file_ui = build_v3_file_ui(app)
                result_index = build_v3_result_index(app)
                comparison = build_v3_comparison(app)
                prepared_blobs, fit_blobs = build_v3_blobs(app)
                prepared_hashes = {
                    key: payload_hash(value)
                    for key, value in prepared_blobs.items()
                }
                fit_hashes = {
                    key: payload_hash(value)
                    for key, value in fit_blobs.items()
                }
                coarse = payload_hash({
                    "file_ui": file_ui, "result_index": result_index,
                    "comparison": comparison,
                    "prepared_hashes": prepared_hashes,
                    "fit_hashes": fit_hashes,
                })
                if coarse == app._app_state.get("_last_cache_coarse_hash"):
                    return
                app._app_state["_last_cache_coarse_hash"] = coarse
            else:
                app._app_state["_last_manifest_hash"] = manifest_hash
                file_ui = build_v3_file_ui(app)
                result_index = build_v3_result_index(app)
                comparison = build_v3_comparison(app)
                prepared_blobs, fit_blobs = build_v3_blobs(app)
                app._app_state.pop("_last_cache_coarse_hash", None)

            self._pending_history_entry = {
                "id": project_id,
                "title": title,
                "cache_path": str(project_dir),
                "files": [str(path) for path in selected_paths],
            }
            self._cache_writer.request_v3_write(
                project_dir, manifest, file_ui, result_index, comparison,
                prepared_blobs, fit_blobs,
                hashes=app._app_state.get("_v3_file_hashes"),
            )
        except Exception as exc:
            try:
                app.status_bar.setText(f"历史项目自动保存失败: {str(exc)[:80]}")
            except Exception:
                pass
            return

    def _on_cache_write_finished(self) -> None:
        app = self.app
        # Store v3 file hashes from worker
        if hasattr(self._cache_writer, "_result_hashes"):
            app._app_state["_v3_file_hashes"] = self._cache_writer._result_hashes
        # Clean up old v2 file if project was migrated
        old_v2 = app._app_state.pop("_old_v2_cache_path", None)
        if old_v2:
            _remove_cache_path(Path(old_v2))
        entry = self._pending_history_entry
        if entry is None:
            return
        self._pending_history_entry = None
        entry["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = [entry]
        history.extend(app._app_state.get("project_history", []))
        result: list[dict] = []
        seen: set[str] = set()
        for item in history:
            item_id = str(item.get("id") or item.get("cache_path") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            result.append(item)
            if len(result) >= 80:
                break
        app._app_state["project_history"] = result
        app.views.refresh_history_panel()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
        except Exception:
            pass

    def schedule_project_autosave(self) -> None:
        if self.app._app_state.get("selected_paths"):
            self._autosave_timer.start()

    def _build_cache_path_map(self, cached_paths: list[Path]) -> dict[str, Path]:
        app = self.app
        path_map: dict[str, Path] = {}
        unresolved: list[Path] = []
        current_paths = [
            Path(path) for path in app._app_state.get("selected_paths", [])
            if Path(path).exists()
        ]
        current_by_name: dict[str, list[Path]] = {}
        for path in current_paths:
            current_by_name.setdefault(path.name.lower(), []).append(path)

        for old_path in cached_paths:
            candidate = _same_file_candidate(old_path)
            if candidate is None:
                matches = current_by_name.get(old_path.name.lower(), [])
                if matches:
                    candidate = max(matches, key=lambda path: _common_tail_score(old_path, path))
            if candidate is not None:
                path_map[_path_key(old_path)] = candidate
            else:
                unresolved.append(old_path)

        if not unresolved:
            return path_map

        root = QFileDialog.getExistingDirectory(
            app,
            "选择移动后的数据根目录",
            str(current_paths[0].parent) if current_paths else "",
        )
        if not root:
            return path_map
        root_path = Path(root)
        indexed: dict[str, list[Path]] = {}
        for old_path in unresolved:
            indexed.setdefault(old_path.name.lower(), [])
        for candidate in root_path.rglob("*"):
            if candidate.is_file() and candidate.name.lower() in indexed:
                indexed[candidate.name.lower()].append(candidate)
        for old_path in unresolved:
            matches = indexed.get(old_path.name.lower(), [])
            if not matches:
                continue
            path_map[_path_key(old_path)] = max(
                matches,
                key=lambda path: _common_tail_score(old_path, path),
            )
        return path_map

    def _remap_cached_path(self, value: str | Path, path_map: dict[str, Path]) -> Path:
        path = Path(value)
        return path_map.get(_path_key(path), path)

    def _remap_file_ui_cache(self, file_ui_cache: dict, path_map: dict[str, Path]) -> dict:
        remapped: dict = {}
        for key, value in file_ui_cache.items():
            remapped[str(self._remap_cached_path(key, path_map))] = value
        return remapped

    def import_cache_dialog(self) -> None:
        app = self.app
        selected_paths = app._app_state.get("selected_paths") or []
        first_path = selected_paths[0] if selected_paths else None
        initial_dir = str(first_path.parent) if first_path else ""
        cache_path, _ = QFileDialog.getOpenFileName(
            app, "选择缓存文件", initial_dir,
            "JSON (*.json);;All files (*.*)"
        )
        if not cache_path:
            return
        self.import_cache_file(Path(cache_path))

    def import_cache_file(self, cache_path: Path | str) -> None:
        from core.serialization import fit_from_dict, prepared_from_dict
        from core.types import ComparisonItem
        from core import cache as c

        app = self.app
        cache_path = Path(cache_path)
        restore_started = False
        try:
            is_history_restore = self._adopt_history_project_for_cache(cache_path)
            if not is_history_restore:
                self._begin_new_project()
            else:
                self._autosave_timer.stop()

            # Detect v3 directory vs v2 single file
            if cache_path.is_dir() and (cache_path / "manifest.json").exists():
                payload = c.load_v3_project_dir(cache_path)
            elif cache_path.is_dir():
                raise FileNotFoundError(f"缓存目录缺少 manifest.json: {cache_path}")
            else:
                payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            # Restore paths
            paths = [Path(p) for p in payload.get("selected_paths", [])]
            path_candidates = list(paths)
            path_candidates.extend(Path(p) for p in payload.get("current_result_keys", {}).keys())
            path_candidates.extend(
                Path(item["key"][0])
                for item in payload.get("result_cache", [])
                if item.get("key") and isinstance(item["key"][0], str)
            )
            path_candidates.extend(
                Path(item["file_path"])
                for item in payload.get("comparison_items", [])
                if item.get("file_path")
            )
            path_map = self._build_cache_path_map(path_candidates)
            restored_paths = []
            for path in paths:
                mapped = self._remap_cached_path(path, path_map)
                if mapped.exists() and mapped not in restored_paths:
                    restored_paths.append(mapped)
            app._app_state["selected_paths"] = restored_paths
            app._app_state["file_ui_cache"] = self._remap_file_ui_cache(
                payload.get("file_ui_cache", {}),
                path_map,
            )
            app._app_state["current_result_keys"] = {
                str(self._remap_cached_path(file_key, path_map)): _with_cache_key_path(
                    c.cache_key_from_json(cache_key),
                    self._remap_cached_path(file_key, path_map),
                )
                for file_key, cache_key in payload.get("current_result_keys", {}).items()
            }
            chart_view_state = payload.get("chart_view_state", {})
            if isinstance(chart_view_state, dict):
                app._app_state["single_plot_view_state"] = chart_view_state.get("single")
                app._app_state["compare_plot_view_state"] = chart_view_state.get("comparison")
            app.views.refresh_file_list()
            # Restore result cache
            result_cache = {}
            for item in payload.get("result_cache", []):
                prepared_by_segment_payload = {
                    int(k): v
                    for k, v in item.get("prepared_by_segment", {}).items()
                    if c.is_prepared_payload(v)
                }
                prepared_payload = item.get("prepared")
                if not c.is_prepared_payload(prepared_payload):
                    prepared_payload = next(iter(prepared_by_segment_payload.values()), None)
                if prepared_payload is None:
                    continue
                cache_key = c.cache_key_from_json(item["key"])
                if cache_key and isinstance(cache_key[0], str):
                    key_path = self._remap_cached_path(cache_key[0], path_map)
                    remapped_key = _with_cache_key_path(cache_key, key_path)
                else:
                    remapped_key = cache_key
                result_cache[remapped_key] = {
                    "prepared": prepared_from_dict(prepared_payload),
                    "fit": fit_from_dict(item["fit"]) if item.get("fit") else None,
                    "prepared_by_segment": {
                        k: prepared_from_dict(v)
                        for k, v in prepared_by_segment_payload.items()
                    },
                    "fit_by_segment": {
                        int(k): fit_from_dict(v)
                        for k, v in item.get("fit_by_segment", {}).items()
                    },
                    "fit_error_by_segment": {
                        int(k): v
                        for k, v in item.get("fit_error_by_segment", {}).items()
                    },
                    "manual_fit_regions": _normalize_manual_regions(item.get("manual_fit_regions", {})),
                    "selected_segment_indices": item.get("selected_segment_indices", []),
                    "active_segment_index": item.get("active_segment_index", 0),
                    "view_state": item.get("view_state"),
                    "limits": item.get("limits"),
                }
            app._app_state["result_cache"] = result_cache
            app._app_state["comparison_items"] = [
                ComparisonItem(
                    item_id=str(item["item_id"]),
                    file_path=self._remap_cached_path(item["file_path"], path_map),
                    file_name=str(item["file_name"]),
                    segment_index=int(item["segment_index"]),
                    prepared=prepared_from_dict(item["prepared"]),
                    fit=fit_from_dict(item["fit"]) if item.get("fit") else None,
                    label=str(item.get("label") or ""),
                    color=str(item.get("color") or COMPARISON_COLORS[int(item["segment_index"]) % len(COMPARISON_COLORS)]),
                    visible=bool(item.get("visible", True)),
                )
                for item in payload.get("comparison_items", [])
                if c.is_prepared_payload(item.get("prepared"))
            ]
            app.comparison.refresh_list()
            if is_history_restore:
                app._app_state["_suppress_next_load_autosave"] = True
                app.views.refresh_history_panel()
            else:
                self.autosave_project_history()
            # Switch to first available
            if app._app_state["selected_paths"]:
                current_path = payload.get("current_path")
                mapped_current = self._remap_cached_path(current_path, path_map) if current_path else None
                if mapped_current not in app._app_state["selected_paths"]:
                    mapped_current = app._app_state["selected_paths"][0]
                if mapped_current is None:
                    return
                app._app_state["tdms_path"] = mapped_current
                self._load_file(mapped_current)
                restore_started = True
            app.status_bar.setText("缓存已导入")
        except Exception as exc:
            QMessageBox.critical(app, "缓存恢复失败", str(exc))
        finally:
            if hasattr(app, "history_workspace") and not restore_started:
                app.history_workspace.set_busy(False)

    def on_history_remove(self, entry_id: str) -> None:
        app = self.app
        history = []
        removed_cache_path: Path | None = None
        for entry in app._app_state.get("project_history", []):
            if str(entry.get("id")) == str(entry_id):
                cache_path = str(entry.get("cache_path") or "")
                removed_cache_path = Path(cache_path) if cache_path else None
                continue
            history.append(entry)
        app._app_state["project_history"] = history
        if removed_cache_path is not None:
            _remove_cache_path(removed_cache_path)
        app.views.refresh_history_panel()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
        except Exception:
            pass

    def on_history_clear(self) -> None:
        app = self.app
        for entry in app._app_state.get("project_history", []):
            cache_path = str(entry.get("cache_path") or "")
            if not cache_path:
                continue
            _remove_cache_path(Path(cache_path))
        app._app_state["project_history"] = []
        app.views.refresh_history_panel()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
        except Exception:
            pass

    # ━━ Palette dispatchers (from FileSegmentPanel / ComparisonPanel) ━━

    def on_palette_scheme_changed(self, scheme_name: str) -> None:
        app = self.app
        if not scheme_name or scheme_name == app.state.palette.active_name:
            return
        app.state.palette.set_active(scheme_name)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_apply(self, mode: str = "sequential") -> None:
        app = self.app
        scheme_name = app.state.palette.active_name
        segments = app._app_state.get("segments", [])
        colors = app._app_state.get("segment_colors", {})
        mapped_colors = _map_palette_colors(
            app.state.palette.colors(scheme_name),
            len(segments),
            mode,
        )
        for position, seg in enumerate(segments):
            idx = seg["index"]
            colors[idx] = mapped_colors[position]
        app.views.refresh_segments()
        self._sync_comparison_colors_for_current_file()
        self._rerender_current()
        self.schedule_project_autosave()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
            mode_label = "插值" if mode == "interpolate" else "逐个"
            app.status_bar.setText(f"配色方案已应用并保存: {scheme_name}（{mode_label}）")
        except Exception as exc:
            app.status_bar.setText(f"配色方案保存失败: {exc}")

    def on_palette_apply_comparison(self, mode: str = "sequential") -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        mapped_colors = _map_palette_colors(
            app.state.palette.colors(app.state.palette.active_name),
            len(items),
            mode,
        )
        for i, item in enumerate(items):
            item.color = mapped_colors[i]
        if hasattr(app.comparison, 'refresh_list'):
            app.comparison.refresh_list()
        if app.state.comparison_mode:
            app.views.render_comparison()
        self.schedule_project_autosave()

    # ━━ Palette sidebar handlers ━━

    def on_palette_scheme_selected(self, scheme_name: str) -> None:
        app = self.app
        if not scheme_name or scheme_name == app.state.palette.active_name:
            return
        app.state.palette.set_active(scheme_name)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_color_changed(self, index: int, new_hex: str) -> None:
        app = self.app
        app.state.palette.set_color(index, new_hex)
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.update_color(index, new_hex)
        if hasattr(app, "palette_workspace"):
            app.views.refresh_palette_workspace()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_count_changed(self, count: int) -> None:
        app = self.app
        app.state.palette.set_count(count)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_color_move(self, index: int, delta: int) -> None:
        app = self.app
        new_index = app.state.palette.move_color(index, delta)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(new_index)
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_color_add(self, index: int = -1) -> None:
        app = self.app
        new_index = app.state.palette.add_color(after_index=index)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(new_index)
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_color_remove(self, indices: list[int] | None = None) -> None:
        app = self.app
        new_index = app.state.palette.remove_colors(indices)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(new_index)
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_colors_reverse(self, indices: list[int] | None = None) -> None:
        app = self.app
        app.state.palette.reverse_colors(indices)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_colors_gradient(self, indices: list[int] | None = None) -> None:
        app = self.app
        app.state.palette.gradient_fill(indices)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_default_reset(self) -> None:
        app = self.app
        app.state.palette.reset_default()
        app.state.palette.set_active("默认方案")
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()
        self.schedule_project_autosave()

    def on_palette_save_as_new(self, base_name: str = "") -> None:
        from PySide6.QtWidgets import QInputDialog
        app = self.app
        name, ok = QInputDialog.getText(None, "新建方案", "请输入方案名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in app.state.palette.schemes:
            QMessageBox.warning(None, "名称冲突", f'方案 "{name}" 已存在')
            return
        app.state.palette.save_copy(name)
        app.views.refresh_palette_controls()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
        except Exception:
            pass

    def on_palette_delete(self, scheme_name: str) -> None:
        app = self.app
        app.state.palette.delete(scheme_name)
        app.views.refresh_palette_controls()
        try:
            from ui.settings import save_app_settings
            save_app_settings(app)
        except Exception:
            pass

    # ━━ Refresh helpers ━━

    def _refresh_segment_panel(self) -> None:
        self.app.views.refresh_segments(rebuild=True)

    def _refresh_palette_controls(self) -> None:
        self.app.views.refresh_palette_controls()

    def _rerender_current(self) -> None:
        app = self.app
        prepared = app._app_state.get("prepared")
        if prepared is None:
            return
        app.views.render_single()

    def _apply_active_palette_to_context(self) -> None:
        app = self.app
        if app.state.comparison_mode:
            for i, item in enumerate(app._app_state.get("comparison_items", [])):
                item.color = app.state.palette.color_at(i)
            if hasattr(app.comparison, "refresh_list"):
                app.comparison.refresh_list()
            app.views.render_comparison()
            return

        segments = app._app_state.get("segments", [])
        if segments:
            colors = app._app_state.setdefault("segment_colors", {})
            for seg in segments:
                idx = int(seg["index"])
                colors[idx] = app.state.palette.color_at(idx)
            app.views.refresh_segments()
            self._sync_comparison_colors_for_current_file()
            self._rerender_current()

    def _sync_comparison_colors_for_current_file(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if path is None:
            return
        colors = app._app_state.get("segment_colors", {})
        for item in app._app_state.get("comparison_items", []):
            if item.file_path != path:
                continue
            item.color = colors.get(item.segment_index, item.color)
        if hasattr(app, "comparison"):
            app.comparison.refresh_list()
