from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ui.controllers.base import BaseAppController
from ui.controllers.worker_utils import stop_worker

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


class BatchExportWorker(QThread):
    """Background worker for batch exporting multiple files/segments."""

    finished = Signal(int, int)  # success_count, fail_count
    error = Signal(str)

    def __init__(self, result_cache: dict, current_result_keys: dict,
                 out_dir: Path, file_name_map: dict[str, str] | None = None):
        super().__init__()
        self.result_cache = result_cache
        self.current_result_keys = current_result_keys
        self.out_dir = out_dir
        self.file_name_map = dict(file_name_map or {})

    def run(self) -> None:
        from core.export import export_processed_txt, export_fit_npz, plot_tafel

        success = 0
        fail = 0
        for path_key, cache_key in self.current_result_keys.items():
            entry = self.result_cache.get(cache_key)
            if entry is None:
                fail += 1
                continue
            prepared = entry.get("prepared")
            fit = entry.get("fit")
            if prepared is None or fit is None:
                fail += 1
                continue
            try:
                stem = Path(path_key).stem
                prefix = (self.file_name_map.get(path_key) or "").strip() or stem
                seg_idx = prepared.segment.index + 1
                base = self.out_dir / f"{prefix}_seg{seg_idx}"
                export_processed_txt(base.with_suffix(".txt"), prepared, fit)
                export_fit_npz(base.with_suffix(".npz"), prepared, fit)
                plot_tafel(base.with_suffix(".png"), prepared, fit)
                success += 1
            except Exception:
                fail += 1
        self.finished.emit(success, fail)


class ExportController(BaseAppController):
    """Handles single, batch, and comparison export."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._batch_worker: BatchExportWorker | None = None

    def export_current(self) -> None:
        app = self.app
        fit = app._app_state.get("fit")
        prepared = app._app_state.get("prepared")
        if fit is None or prepared is None:
            QMessageBox.warning(app, "提示", "请先运行拟合")
            return

        path = app._app_state.get("tdms_path")
        if path is None:
            return

        export_name = app.state.files.display_name(path)
        default_name = f"{export_name}_tafel.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出结果",
            str(path.parent / default_name),
            "Text (*.txt);;NumPy NPZ (*.npz);;PNG Image (*.png)",
        )
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".txt":
                from core.export import export_processed_txt
                export_processed_txt(Path(file_path), prepared, fit)
            elif ext == ".npz":
                from core.export import export_fit_npz
                export_fit_npz(Path(file_path), prepared, fit)
            elif ext == ".png":
                app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
            app.status_bar.setText(f"已导出: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.critical(app, "导出失败", str(exc))

    def run_batch(self) -> None:
        app = self.app
        cache = app._app_state.get("result_cache", {})
        keys = app._app_state.get("current_result_keys", {})
        if not cache or not keys:
            QMessageBox.warning(app, "提示", "没有可用的拟合结果")
            return

        dir_path = QFileDialog.getExistingDirectory(app, "选择导出目录")
        if not dir_path:
            return

        file_name_map = {
            str(p): app.state.files.display_name(p)
            for p in app._app_state.get("selected_paths", [])
        }

        # Clean up previous worker
        stop_worker(self._batch_worker)

        app.status_bar.setText("正在批量导出…")
        self._batch_worker = BatchExportWorker(
            cache, keys, Path(dir_path), file_name_map,
        )
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(self._on_batch_error)
        self._batch_worker.start()

    def _on_batch_finished(self, success: int, fail: int) -> None:
        self.app.status_bar.setText(
            f"批量导出完成: {success} 成功, {fail} 失败"
        )

    def _on_batch_error(self, msg: str) -> None:
        self.app.status_bar.setText(f"批量导出错误: {msg[:60]}")

    def export_comparison(self) -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        if not items:
            QMessageBox.warning(app, "提示", "没有对比项")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出对比图",
            "comparison.png",
            "PNG Image (*.png);;PDF (*.pdf)",
        )
        if not file_path:
            return

        from core.comparison import render_comparison
        if app._app_state.get("comparison_mode"):
            render_comparison(app)
        app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
        app.status_bar.setText(f"对比图已导出: {Path(file_path).name}")
