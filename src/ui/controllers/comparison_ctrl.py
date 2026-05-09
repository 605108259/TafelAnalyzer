from __future__ import annotations

from typing import TYPE_CHECKING

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

    def add_from_current(self) -> None:
        """Add all checked segments from the current file to comparison."""
        app = self.app
        state = app.state
        path = state.files.current_path
        if not path:
            return
        checked = set(state.segments.selected_indices)
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        if not checked:
            QMessageBox.warning(app, "提示", "请先勾选要对比的分段")
            return
        alias = state.files.display_name(path)
        added = 0
        for seg_idx in sorted(checked):
            seg_prepared = prepared_by.get(seg_idx)
            if seg_prepared is None:
                continue
            item_id = comp.comparison_item_id(path, seg_idx)
            if state.comparison.has_item(item_id):
                continue
            color = app._app_state.get("segment_colors", {}).get(
                int(seg_idx),
                COMPARISON_COLORS[int(seg_idx) % len(COMPARISON_COLORS)],
            )
            if state.comparison.add(ComparisonItem(
                item_id=item_id,
                file_path=path,
                file_name=alias,
                segment_index=seg_idx,
                prepared=seg_prepared,
                fit=fit_by.get(seg_idx),
                label=f"{alias}-第{seg_idx + 1}段",
                color=color,
                visible=True,
            )):
                added += 1
        if added == 0:
            QMessageBox.warning(app, "提示", "勾选的分段已在对比列表中")
            return
        self.refresh_list()

    def add_all_processed(self) -> None:
        app = self.app
        state = app.state
        path = state.files.current_path
        if not path:
            return
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        alias = state.files.display_name(path)

        for seg_idx in prepared_by:
            item_id = comp.comparison_item_id(path, seg_idx)
            if state.comparison.has_item(item_id):
                continue
            color = app._app_state.get("segment_colors", {}).get(
                int(seg_idx),
                COMPARISON_COLORS[int(seg_idx) % len(COMPARISON_COLORS)],
            )
            state.comparison.add(ComparisonItem(
                item_id=item_id,
                file_path=path,
                file_name=alias,
                segment_index=seg_idx,
                prepared=prepared_by[seg_idx],
                fit=fit_by.get(seg_idx),
                label=f"{alias}-第{seg_idx + 1}段",
                color=color,
                visible=True,
            ))
        self.refresh_list()

    def delete_selected(self) -> None:
        self.app.state.comparison.delete_highlighted()
        self.refresh_list()

    def remove_by_id(self, item_id: str) -> None:
        self.app.state.comparison.remove(item_id)
        self.refresh_list()

    def highlight_item(self, row: int) -> None:
        self.app.state.comparison.set_highlight(row)
        self.app.views.refresh_comparison_list(rebuild=False)
        self._rerender()

    def move_up(self) -> None:
        self.app.state.comparison.move_highlight(-1)
        self.refresh_list()

    def move_down(self) -> None:
        self.app.state.comparison.move_highlight(1)
        self.refresh_list()

    def clear_all(self) -> None:
        self.app.state.comparison.clear()
        self.refresh_list()

    def toggle_visibility(self, item_id: str, visible: bool) -> None:
        self.app.state.comparison.set_visible(item_id, visible)
        self._rerender()

    def update_color(self, item_id: str, color: str) -> None:
        self.app.state.comparison.set_color(item_id, color)
        self.refresh_list()

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
        self._rerender()

    def refresh_list(self) -> None:
        self.app.views.refresh_comparison_list()
        self._update_summary()
        self._rerender()

    def _update_summary(self) -> None:
        # Summary table removed from comparison view; kept for export only.
        pass

    def _rerender(self) -> None:
        if self.app.state.comparison_mode:
            self.app.views.render_comparison()
