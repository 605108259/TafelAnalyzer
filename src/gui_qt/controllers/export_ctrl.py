from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from gui_qt.controllers.base import BaseAppController

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class ExportController(BaseAppController):
    """Handles single, batch, and comparison export."""

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

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出结果",
            str(path.parent / f"{path.stem}_tafel.txt"),
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
        dir_path = QFileDialog.getExistingDirectory(app, "选择导出目录")
        if not dir_path:
            return
        app.status_bar.setText(f"批量导出到 {dir_path} (待实现)")

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

        from gui.comparison import render_comparison
        if app._app_state.get("comparison_mode"):
            render_comparison(app)
        app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
        app.status_bar.setText(f"对比图已导出: {Path(file_path).name}")
