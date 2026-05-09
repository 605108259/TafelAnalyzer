from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import POTENTIAL_PREFERRED_NAMES, CURRENT_PREFERRED_NAMES, COMPARISON_COLORS
from core.utils import pick_channel_name
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
            palette_colors[min(source_count - 1, int(i * (source_count - 1) / target_count))]
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


class FileLoadWorker(QThread):
    """Background worker for loading file data."""

    finished = Signal(object, object, object, object)  # channels, potential_f, current_f, segments
    error = Signal(str)

    def __init__(self, file_path: Path, potential_formula: str, current_formula: str):
        super().__init__()
        self.file_path = file_path
        self.potential_formula = potential_formula
        self.current_formula = current_formula

    def run(self):
        try:
            channels = read_data_all_channels(self.file_path)
            formulas = self._resolve_formulas(channels)
            segments = build_segment_infos(channels, formulas[0])
            self.finished.emit(channels, formulas[0], formulas[1], segments)
        except Exception as exc:
            self.error.emit(str(exc))

    def _resolve_formulas(self, channels: dict) -> tuple[str, str]:
        def try_or_default(text: str, preferred: list[str]) -> str:
            raw = text.strip()
            if raw:
                try:
                    normalize_formula(channels, raw, preferred)
                    return raw
                except Exception:
                    pass
            return f"[{pick_channel_name(channels, preferred)}]"
        return (
            try_or_default(self.potential_formula, POTENTIAL_PREFERRED_NAMES),
            try_or_default(self.current_formula, CURRENT_PREFERRED_NAMES),
        )


class FileController(BaseAppController):
    """Manages file loading, switching, removal, palette, and segment interaction."""

    file_loaded = Signal()
    file_load_failed = Signal(str)

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FileLoadWorker | None = None
        if hasattr(app, "views"):
            app.views.refresh_palette_controls()

    # ━━ File operations ━━

    def on_files_loaded(self, paths: list[Path]) -> None:
        app = self.app
        app.state.files.merge_paths(paths)
        app.views.refresh_file_list()
        if paths:
            self._load_file(paths[0])

    def on_file_selected(self, path: Path) -> None:
        self.app.file_segment_panel.set_current_file(path)
        self._load_file(path)

    def on_file_renamed(self, path: Path, new_name: str) -> None:
        app = self.app
        app.state.files.set_alias(path, new_name)
        app.state.comparison.sync_file_alias(path, app.state.files.display_name(path))
        app.views.refresh_file_list()
        app.comparison.refresh_list()

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
        app.file_segment_panel.set_segments([], 0, set(), {}, {})
        app.chart.clear_figure()
        # Clean up previous worker
        stop_worker(self._worker)
        app.status_bar.setText(f"正在加载 {path.name} …")
        formulas = app.toolbar.get_formulas()
        self._worker = FileLoadWorker(path, formulas[0], formulas[1])
        self._worker.generation = generation
        self._worker.finished.connect(self._on_load_finished_from_worker)
        self._worker.error.connect(self._on_load_error_from_worker)
        self._worker.start()

    def _on_load_finished_from_worker(self, channels, pot_f, cur_f, segments) -> None:
        worker = self.sender()
        if worker is None:
            return
        self._on_load_finished(channels, pot_f, cur_f, segments, worker.file_path, worker.generation)

    def _on_load_error_from_worker(self, msg) -> None:
        worker = self.sender()
        if worker is None:
            return
        self._on_load_error(msg, worker.file_path, worker.generation)

    def _on_load_finished(self, channels, pot_f, cur_f, segments, expected_path=None, generation: int | None = None) -> None:
        app = self.app
        if expected_path is not None and app._app_state.get("tdms_path") != expected_path:
            return
        if not app.state.operations.is_current(generation):
            return
        scheme_name = app.state.palette.active_name
        segment_colors = {}
        for s in segments:
            idx = s.index
            color = app.state.palette.color_at(idx, scheme_name)
            if color:
                segment_colors[idx] = color
        app._app_state["_precomputed_segments"] = segments
        app.state.analysis.apply_loaded_file(
            channels=channels,
            segment_infos=segments,
            segment_colors=segment_colors,
        )

        # Update toolbar formulas
        app.toolbar.set_formulas(pot_f, cur_f)

        # Update segment panel
        app.views.refresh_segments(rebuild=True)

        # Update toolbar params
        app.toolbar.set_params(app._app_state.get("saved_parameter_defaults", {}))

        # Update status
        path = app._app_state["tdms_path"]
        app.file_segment_panel.set_current_file(path)
        app.file_segment_panel.set_processed(path)
        app.status_bar.setText(f"已加载 {path.name}")

        # Clear chart
        app.chart.clear_figure()
        self.file_loaded.emit()
        app.fitting.run_fit()

    def _on_load_error(self, msg: str, expected_path=None, generation: int | None = None) -> None:
        if expected_path is not None and self.app._app_state.get("tdms_path") != expected_path:
            return
        if not self.app.state.operations.is_current(generation):
            return
        self.app.status_bar.setText("加载失败")
        QMessageBox.critical(self.app, "加载失败", msg)

    # ━━ File removal ━━

    def on_file_removed(self, path: Path) -> None:
        app = self.app
        app.state.files.remove_path(path)
        app.state.comparison.remove_file_items(path)
        app.views.refresh_file_list()
        app.comparison.refresh_list()
        # Switch to next file or clear
        remaining = app.state.files.selected_paths
        if remaining:
            app.state.files.set_current_path(remaining[0])
            self._load_file(remaining[0])
        else:
            app.state.reset_current_file()
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
            else:
                app.fitting.run_fit()
        else:
            self._rerender_current()

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

    def on_select_all(self) -> None:
        app = self.app
        app.state.segments.select_all_loaded()
        app.views.refresh_segments()
        app.fitting.run_fit()

    def on_clear_all(self) -> None:
        app = self.app
        app.state.segments.clear_selection()
        app.views.refresh_segments()
        from core.rendering import draw_placeholder
        draw_placeholder(app)

    # ━━ Cache import ━━

    def import_cache_dialog(self) -> None:
        from core.serialization import fit_from_dict, prepared_from_dict
        from core.types import ComparisonItem
        from core import cache as c

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
        try:
            payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            # Restore paths
            paths = [Path(p) for p in payload.get("selected_paths", [])]
            app._app_state["selected_paths"] = [p for p in paths if p.exists()]
            app._app_state["file_ui_cache"] = payload.get("file_ui_cache", {})
            app.views.refresh_file_list()
            # Restore result cache
            app._app_state["result_cache"] = {
                c.cache_key_from_json(item["key"]): {
                    "prepared": prepared_from_dict(item["prepared"]),
                    "fit": fit_from_dict(item["fit"]) if item.get("fit") else None,
                    "prepared_by_segment": {
                        int(k): prepared_from_dict(v)
                        for k, v in item.get("prepared_by_segment", {}).items()
                    },
                    "fit_by_segment": {
                        int(k): fit_from_dict(v)
                        for k, v in item.get("fit_by_segment", {}).items()
                    },
                    "fit_error_by_segment": {
                        int(k): v
                        for k, v in item.get("fit_error_by_segment", {}).items()
                    },
                    "selected_segment_indices": item.get("selected_segment_indices", []),
                    "active_segment_index": item.get("active_segment_index", 0),
                    "view_state": item.get("view_state"),
                    "limits": item.get("limits"),
                }
                for item in payload.get("result_cache", [])
            }
            app._app_state["comparison_items"] = [
                ComparisonItem(
                    item_id=str(item["item_id"]),
                    file_path=Path(item["file_path"]),
                    file_name=str(item["file_name"]),
                    segment_index=int(item["segment_index"]),
                    prepared=prepared_from_dict(item["prepared"]),
                    fit=fit_from_dict(item["fit"]) if item.get("fit") else None,
                    label=str(item.get("label") or ""),
                    color=str(item.get("color") or COMPARISON_COLORS[int(item["segment_index"]) % len(COMPARISON_COLORS)]),
                    visible=bool(item.get("visible", True)),
                )
                for item in payload.get("comparison_items", [])
                if item.get("prepared") is not None
            ]
            app.comparison.refresh_list()
            # Switch to first available
            if app._app_state["selected_paths"]:
                app._app_state["tdms_path"] = app._app_state["selected_paths"][0]
                self._load_file(app._app_state["selected_paths"][0])
            app.status_bar.setText("缓存已导入")
        except Exception as exc:
            QMessageBox.critical(app, "缓存恢复失败", str(exc))

    # ━━ Palette dispatchers (from FileSegmentPanel / ComparisonPanel) ━━

    def on_palette_scheme_changed(self, scheme_name: str) -> None:
        app = self.app
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

    # ━━ Palette sidebar handlers ━━

    def on_palette_scheme_selected(self, scheme_name: str) -> None:
        app = self.app
        app.state.palette.set_active(scheme_name)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_color_changed(self, index: int, new_hex: str) -> None:
        app = self.app
        app.state.palette.set_color(index, new_hex)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_count_changed(self, count: int) -> None:
        app = self.app
        app.state.palette.set_count(count)
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_color_move(self, index: int, delta: int) -> None:
        app = self.app
        new_index = app.state.palette.move_color(index, delta)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(new_index)
        self._apply_active_palette_to_context()

    def on_palette_color_add(self, index: int = -1) -> None:
        app = self.app
        new_index = app.state.palette.add_color(after_index=index)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(new_index)
        self._apply_active_palette_to_context()

    def on_palette_color_remove(self, index: int) -> None:
        app = self.app
        app.state.palette.remove_color(index)
        app.views.refresh_palette_controls()
        if hasattr(app, "palette_sidebar"):
            app.palette_sidebar.set_selected_index(max(0, index - 1))
        self._apply_active_palette_to_context()

    def on_palette_colors_reverse(self) -> None:
        app = self.app
        app.state.palette.reverse_colors()
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_colors_gradient(self) -> None:
        app = self.app
        app.state.palette.gradient_fill()
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

    def on_palette_default_reset(self) -> None:
        app = self.app
        app.state.palette.reset_default()
        app.state.palette.set_active("默认方案")
        app.views.refresh_palette_controls()
        self._apply_active_palette_to_context()

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

    def on_palette_delete(self, scheme_name: str) -> None:
        app = self.app
        app.state.palette.delete(scheme_name)
        app.views.refresh_palette_controls()

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

    def _reset_current_file_state(self) -> None:
        app = self.app
        app.state.reset_current_file()

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

    def _refresh_palette_sidebar(self) -> None:
        self.app.views.refresh_palette_sidebar()
