from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import POTENTIAL_PREFERRED_NAMES, CURRENT_PREFERRED_NAMES
from core.utils import pick_channel_name
from gui import palette as p
from gui_qt.controllers.base import BaseAppController
from gui.rendering import draw_placeholder_fig

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
    """Manages file loading, switching, and removal."""

    file_loaded = Signal()
    file_load_failed = Signal(str)

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FileLoadWorker | None = None

    def on_files_loaded(self, paths: list[Path]) -> None:
        app = self.app
        app._app_state["selected_paths"] = paths
        app.file_panel.update_info(
            f"已选择 {len(paths)} 个文件"
        )
        self._load_file(paths[0])

    def on_file_selected(self, path: Path) -> None:
        self._load_file(path)

    def _load_file(self, path: Path) -> None:
        app = self.app
        app.status_bar.setText(f"正在加载 {path.name} …")
        app._app_state["tdms_path"] = path
        formulas = app.formula_panel.get_formulas()
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

        # Update formula panel
        app.formula_panel.hide_error()
        app.formula_panel.potential_input.setText(pot_f)
        app.formula_panel.current_input.setText(cur_f)
        app.formula_panel.set_channels(list(channels.keys()))

        # Update segment panel
        app.segment_panel.set_segments(
            app._app_state["segments"], 0,
            app._app_state["segment_colors"],
            {},
        )

        # Update param bar defaults
        app.param_bar.set_defaults(app._app_state.get("saved_parameter_defaults", {}))

        # Update status
        path = app._app_state["tdms_path"]
        app.file_panel.update_info(
            f"{len(channels)} channels · {segment_count} segments"
        )
        app.file_panel.set_processed(path)
        app.status_bar.setText(f"已加载 {path.name}")

        # Draw placeholder
        draw_placeholder_fig(
            app.chart.fig, app.chart.canvas,
            app.chart.axes,
        )
        self.file_loaded.emit()

    def _on_load_error(self, msg: str) -> None:
        self.app.status_bar.setText("加载失败")
        QMessageBox.critical(self.app, "加载失败", msg)
