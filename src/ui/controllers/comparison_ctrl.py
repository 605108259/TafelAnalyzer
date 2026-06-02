from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from core.types import ComparisonItem, COMPARISON_COLORS
from ui.controllers.base import BaseAppController
from core import comparison as comp

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


class ComparisonController(BaseAppController):
    """Manages comparison items CRUD and rendering."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._render_token = 0

    def add_from_current(self) -> None:
        """Add all checked segments from the current file to comparison."""
        app = self.app
        state = app.state
        path = state.files.current_path
        if not path:
            return
        checked = {int(index) for index in state.segments.selected_indices}
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        if not checked:
            QMessageBox.warning(app, "提示", "请先勾选要对比的分段")
            return
        alias = state.files.display_name(path)
        added = 0
        updated = 0
        for seg_idx in sorted(checked):
            seg_prepared = prepared_by.get(seg_idx)
            if seg_prepared is None:
                continue
            item_id = comp.comparison_item_id(path, seg_idx)
            color = app._app_state.get("segment_colors", {}).get(
                int(seg_idx),
                COMPARISON_COLORS[int(seg_idx) % len(COMPARISON_COLORS)],
            )
            inserted = state.comparison.upsert(ComparisonItem(
                item_id=item_id,
                file_path=path,
                file_name=alias,
                segment_index=seg_idx,
                prepared=seg_prepared,
                fit=fit_by.get(seg_idx),
                label=f"{alias}-第{seg_idx + 1}段",
                color=color,
                visible=True,
            ))
            if inserted:
                added += 1
            else:
                updated += 1
        if added == 0 and updated == 0:
            QMessageBox.warning(app, "提示", "勾选的分段还没有可用的拟合/处理结果")
            return
        self.refresh_list()
        if updated:
            app.status_bar.setText(f"对比列表已更新 {updated} 项，新增 {added} 项")
        if hasattr(app, "files"):
            app.files.schedule_project_autosave()

    def remove_by_id(self, item_id: str) -> None:
        self.app.state.comparison.remove(item_id)
        self.refresh_list()
        self._autosave_project()

    def highlight_item(self, row: int) -> None:
        self.app.state.comparison.set_highlight(row)
        self.app.views.refresh_comparison_list(rebuild=False)
        self._schedule_rerender()

    def move_up(self) -> None:
        moved = self.app.state.comparison.move_highlight(-1)
        self._sync_after_row_move(moved)
        self._autosave_project()

    def move_down(self) -> None:
        moved = self.app.state.comparison.move_highlight(1)
        self._sync_after_row_move(moved)
        self._autosave_project()

    def clear_all(self) -> None:
        self.app.state.comparison.clear()
        self.refresh_list()
        self._autosave_project()

    def toggle_visibility(self, item_id: str, visible: bool) -> None:
        self.app.state.comparison.set_visible(item_id, visible)
        self._schedule_rerender()
        self._autosave_project()

    def select_all_visible(self) -> None:
        self.app.state.comparison.set_all_visible(True)
        self.refresh_list()
        self._autosave_project()

    def select_none_visible(self) -> None:
        self.app.state.comparison.set_all_visible(False)
        self.refresh_list()
        self._autosave_project()

    def update_color(self, item_id: str, color: str) -> None:
        self.app.state.comparison.set_color(item_id, color)
        self.refresh_list()
        self._autosave_project()

    def set_lsv_style(self, style: str) -> None:
        normalized = comp.normalize_lsv_style(style)
        if self.app._app_state.get("comparison_lsv_style") == normalized:
            return
        self.app._app_state["comparison_lsv_style"] = normalized
        self._rerender()
        self._save_settings()

    def set_tafel_fit_window(self, enabled: bool) -> None:
        value = bool(enabled)
        if bool(self.app._app_state.get("comparison_tafel_fit_window", False)) == value:
            return
        self.app._app_state["comparison_tafel_fit_window"] = value
        self.app._app_state["compare_plot_view_state"] = None
        self.app._app_state["compare_plot_default_view_state"] = None
        self._rerender()
        self._save_settings()

    def set_legend_visible(self, visible: bool) -> None:
        value = bool(visible)
        if bool(self.app._app_state.get("comparison_show_legend", True)) == value:
            return
        self.app._app_state["comparison_show_legend"] = value
        self._rerender()
        self._save_settings()

    def rename(self, item_id: str, new_name: str) -> None:
        item = self.app.state.comparison.item_by_id(item_id)
        display_name = self.app.state.comparison.rename(item_id, new_name)
        if display_name and item is not None:
            self.app.views.update_comparison_name(
                item_id,
                display_name,
                "",
            )
            self.app.status_bar.setText(f"已重命名对比项: {display_name}")
        else:
            self.app.status_bar.setText("重命名失败: 未找到对比项")
        self._schedule_rerender()
        if display_name:
            self._autosave_project()

    def refresh_list(self) -> None:
        self.app.views.refresh_comparison_list()
        self._update_summary()
        self._schedule_rerender()

    def _update_summary(self) -> None:
        # Summary table removed from comparison view; kept for export only.
        pass

    def _rerender(self) -> None:
        if self.app.state.comparison_mode:
            self.app.views.render_comparison()

    def _schedule_rerender(self, delay_ms: int = 80) -> None:
        if not self.app.state.comparison_mode:
            return
        self._render_token += 1
        token = self._render_token

        def render_if_current() -> None:
            if token != self._render_token:
                return
            self._rerender()

        QTimer.singleShot(delay_ms, render_if_current)

    def _sync_after_row_move(self, moved: tuple[int, int] | None) -> None:
        if moved is None:
            self.app.views.refresh_comparison_list(rebuild=False)
            return
        from_row, to_row = moved
        panel_moved = False
        if hasattr(self.app, "comparison_panel"):
            panel_moved = self.app.comparison_panel.move_row(from_row, to_row)
        self.app.views.refresh_comparison_list(rebuild=not panel_moved)
        self._update_summary()
        self._schedule_rerender()

    def _autosave_project(self) -> None:
        if hasattr(self.app, "files"):
            self.app.files.schedule_project_autosave()

    def _save_settings(self) -> None:
        try:
            from ui.settings import save_app_settings
            save_app_settings(self.app)
        except Exception:
            pass
