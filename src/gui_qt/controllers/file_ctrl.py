from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import POTENTIAL_PREFERRED_NAMES, CURRENT_PREFERRED_NAMES
from core.utils import pick_channel_name
from gui_qt.controllers.base import BaseAppController

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


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

    # ━━ File operations ━━

    def on_files_loaded(self, paths: list[Path]) -> None:
        app = self.app
        app._app_state["selected_paths"] = paths
        self._load_file(paths[0])

    def on_file_selected(self, path: Path) -> None:
        self._load_file(path)

    def _load_file(self, path: Path) -> None:
        app = self.app
        app.status_bar.setText(f"正在加载 {path.name} …")
        app._app_state["tdms_path"] = path
        formulas = app.toolbar.get_formulas()
        self._worker = FileLoadWorker(path, formulas[0], formulas[1])
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_load_finished(self, channels, pot_f, cur_f, segments) -> None:
        app = self.app
        app._app_state["channels"] = channels
        app._app_state["segments"] = [{"index": s.index, "label": s.label} for s in segments]
        app._app_state["segment_colors"] = {}
        segment_count = len(segments)

        # Update toolbar formulas
        app.toolbar.set_formulas(pot_f, cur_f)

        # Update segment panel
        app.file_segment_panel.set_segments(
            app._app_state["segments"], 0,
            set(app._app_state.get("selected_segment_indices", [])),
            app._app_state["segment_colors"],
            {},
        )

        # Update toolbar params
        app.toolbar.set_params(app._app_state.get("saved_parameter_defaults", {}))

        # Update status
        path = app._app_state["tdms_path"]
        app.file_segment_panel.set_processed(path)
        app.status_bar.setText(f"已加载 {path.name}")

        # Clear chart
        app.chart.clear_figure()
        self.file_loaded.emit()

    def _on_load_error(self, msg: str) -> None:
        self.app.status_bar.setText("加载失败")
        QMessageBox.critical(self.app, "加载失败", msg)

    # ━━ File removal ━━

    def on_file_removed(self, path: Path) -> None:
        app = self.app
        # Remove from state
        current_key = str(path)
        app._app_state.get("file_ui_cache", {}).pop(current_key, None)
        app._app_state.get("current_result_keys", {}).pop(current_key, None)
        app._app_state["comparison_items"] = [
            item for item in app._app_state.get("comparison_items", [])
            if item.file_path != path
        ]
        # Remove from selected_paths
        if path in app._app_state["selected_paths"]:
            app._app_state["selected_paths"].remove(path)
        # Switch to next file or clear
        remaining = app._app_state.get("selected_paths", [])
        if remaining:
            app._app_state["tdms_path"] = remaining[0]
            self._load_file(remaining[0])
        else:
            app._app_state["tdms_path"] = None
            app._app_state["channels"] = None
            app._app_state["segments"] = []
            app._app_state["segment_colors"] = {}
            app._app_state["prepared"] = None
            app._app_state["fit"] = None
            app._app_state["prepared_by_segment"] = {}
            app._app_state["fit_by_segment"] = {}
            app._app_state["fit_error_by_segment"] = {}
            app._app_state["selected_segment_indices"] = []
            app._app_state["active_segment_index"] = 0
            app.chart.clear_figure()
            app.status_bar.setText("等待选择数据文件")

    # ━━ Segment interaction ━━

    def on_segment_activated(self, index: int) -> None:
        app = self.app
        app._app_state["active_segment_index"] = index
        # Auto-select the active segment
        selected = set(app._app_state.get("selected_segment_indices", []))
        selected.add(index)
        app._app_state["selected_segment_indices"] = sorted(selected)
        self._refresh_segment_panel()
        app.fitting.run_fit()

    def on_segment_toggled(self, index: int, checked: bool) -> None:
        app = self.app
        selected = set(app._app_state.get("selected_segment_indices", []))
        if checked:
            selected.add(index)
        else:
            selected.discard(index)
        app._app_state["selected_segment_indices"] = sorted(selected)
        self._refresh_segment_panel()

    def on_segment_color(self, index: int, _dummy: str = "") -> None:
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            app = self.app
            app._app_state["segment_colors"][index] = color.name()
            self._refresh_segment_panel()

    def on_select_all(self) -> None:
        app = self.app
        segments = app._app_state.get("segments", [])
        app._app_state["selected_segment_indices"] = [s["index"] for s in segments]
        self._refresh_segment_panel()
        app.fitting.run_fit()

    def on_clear_all(self) -> None:
        app = self.app
        app._app_state["selected_segment_indices"] = []
        self._refresh_segment_panel()

    def on_export_name_changed(self, name: str) -> None:
        pass  # ExportController handles this via file_segment_panel.get_export_name()

    # ━━ Cache import ━━

    def import_cache_dialog(self) -> None:
        from gui.serialization import fit_from_dict, prepared_from_dict
        from core.types import ComparisonItem
        from gui import cache as c

        app = self.app
        first_path = app._app_state.get("selected_paths", [None])[0]
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
            # Restore result cache
            app._app_state["result_cache"] = {
                c.cache_key_from_json(item["key"]): {
                    "prepared": prepared_from_dict(item["prepared"]),
                    "fit": fit_from_dict(item["fit"]) if item.get("fit") else None,
                }
                for item in payload.get("result_cache", [])
            }
            # Switch to first available
            if app._app_state["selected_paths"]:
                app._app_state["tdms_path"] = app._app_state["selected_paths"][0]
                self._load_file(app._app_state["selected_paths"][0])
            app.status_bar.setText("缓存已导入")
        except Exception as exc:
            QMessageBox.critical(app, "缓存恢复失败", str(exc))

    # ━━ Palette dispatchers (from FileSegmentPanel / ComparisonPanel) ━━

    def on_palette_scheme_changed(self, scheme_name: str) -> None:
        self.app._app_state["active_palette_scheme"] = scheme_name

    def on_palette_apply(self) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        scheme = app._app_state.get("palette_schemes", {}).get(scheme_name, {})
        segments = app._app_state.get("segments", [])
        colors = app._app_state.get("segment_colors", {})
        for seg in segments:
            idx = seg["index"]
            if str(idx) in scheme:
                colors[idx] = scheme[str(idx)]
        self._refresh_segment_panel()

    def on_palette_apply_comparison(self) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        scheme = app._app_state.get("palette_schemes", {}).get(scheme_name, {})
        for i, item in enumerate(app._app_state.get("comparison_items", [])):
            color_key = str(i % max(len(scheme), 1))
            item.color = scheme.get(color_key, "#94a3b8")
        if hasattr(app.comparison, 'refresh_list'):
            app.comparison.refresh_list()

    # ━━ Palette sidebar handlers ━━

    def on_palette_scheme_selected(self, scheme_name: str) -> None:
        app = self.app
        app._app_state["active_palette_scheme"] = scheme_name
        app._update_palette_workspace()

    def on_palette_color_changed(self, index: int, new_hex: str) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        schemes = app._app_state.setdefault("palette_schemes", {})
        schemes.setdefault(scheme_name, {})[str(index)] = new_hex
        app._update_palette_workspace()

    def on_palette_count_changed(self, count: int) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        app._app_state.setdefault("palette_scheme_slot_counts", {})[scheme_name] = count
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    def on_palette_save_as_new(self, base_name: str = "") -> None:
        from PySide6.QtWidgets import QInputDialog
        app = self.app
        name, ok = QInputDialog.getText(None, "新建方案", "请输入方案名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in app._app_state.get("palette_schemes", {}):
            QMessageBox.warning(None, "名称冲突", f'方案 "{name}" 已存在')
            return
        current = app._app_state.get("active_palette_scheme", "默认方案")
        current_colors = app._app_state.get("palette_schemes", {}).get(current, {})
        current_count = app._app_state.get("palette_scheme_slot_counts", {}).get(current, 8)
        app._app_state.setdefault("palette_schemes", {})[name] = dict(current_colors)
        app._app_state.setdefault("palette_scheme_slot_counts", {})[name] = current_count
        app._app_state["active_palette_scheme"] = name
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    def on_palette_delete(self, scheme_name: str) -> None:
        app = self.app
        schemes = app._app_state.get("palette_schemes", {})
        if len(schemes) <= 1:
            return
        schemes.pop(scheme_name, None)
        app._app_state.get("palette_scheme_slot_counts", {}).pop(scheme_name, None)
        app._app_state["active_palette_scheme"] = next(iter(schemes.keys()))
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    # ━━ Refresh helpers ━━

    def _refresh_segment_panel(self) -> None:
        app = self.app
        p = app.file_segment_panel
        segments = app._app_state.get("segments", [])
        p.set_segments(
            segments,
            active_index=app._app_state.get("active_segment_index", 0),
            checked_indices=set(app._app_state.get("selected_segment_indices", [])),
            colors=app._app_state.get("segment_colors", {}),
            fit_by_segment=app._app_state.get("fit_by_segment", {}),
        )

    def _refresh_palette_sidebar(self) -> None:
        app = self.app
        schemes = list(app._app_state.get("palette_schemes", {}).keys())
        active = app._app_state.get("active_palette_scheme", "默认方案")
        app.palette_sidebar.set_schemes(schemes, active)
        slot_count = app._app_state.get("palette_scheme_slot_counts", {}).get(active, 8)
        scheme_colors = app._app_state.get("palette_schemes", {}).get(active, {})
        colors = [scheme_colors.get(str(i), "#94a3b8") for i in range(slot_count)]
        names = [f"第{i+1}段" for i in range(slot_count)]
        app.palette_sidebar.set_colors(colors, names)
        app.palette_sidebar.count_combo.blockSignals(True)
        app.palette_sidebar.count_combo.setCurrentText(str(slot_count))
        app.palette_sidebar.count_combo.blockSignals(False)
