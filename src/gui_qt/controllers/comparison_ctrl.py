from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from core.types import ComparisonItem
from gui_qt.controllers.base import BaseAppController
from gui import palette as p
from gui import comparison as comp

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class ComparisonController(BaseAppController):
    """Manages comparison items CRUD and rendering."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)

    def add_from_current(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        active_idx = app._app_state.get("active_segment_index", 0)
        prepared = app._app_state.get("prepared")
        fit = app._app_state.get("fit")
        if prepared is None:
            QMessageBox.warning(app, "提示", "请先运行拟合")
            return

        item_id = comp.comparison_item_id(path, active_idx)
        existing = [it for it in app._app_state.get("comparison_items", [])
                    if it.item_id == item_id]
        if existing:
            QMessageBox.warning(app, "提示", "该项目已在对比列表中")
            return

        color = p.get_segment_color(app, active_idx, file_path=path)
        item = ComparisonItem(
            item_id=item_id,
            file_path=path,
            file_name=path.name,
            segment_index=active_idx,
            prepared=prepared,
            fit=fit,
            label=f"{path.stem}-第{active_idx + 1}段",
            color=color,
            visible=True,
        )
        app._app_state.setdefault("comparison_items", []).append(item)
        self.refresh_list()

    def add_all_processed(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        items = app._app_state.setdefault("comparison_items", [])

        for seg_idx in prepared_by:
            item_id = comp.comparison_item_id(path, seg_idx)
            if any(it.item_id == item_id for it in items):
                continue
            color = p.get_segment_color(app, seg_idx, file_path=path)
            items.append(ComparisonItem(
                item_id=item_id,
                file_path=path,
                file_name=path.name,
                segment_index=seg_idx,
                prepared=prepared_by[seg_idx],
                fit=fit_by.get(seg_idx),
                label=f"{path.stem}-第{seg_idx + 1}段",
                color=color,
                visible=True,
            ))
        self.refresh_list()

    def delete_selected(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if 0 <= current < len(items):
            items.pop(current)
            self.refresh_list()

    def move_up(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current > 0:
            items[current], items[current - 1] = items[current - 1], items[current]
            self.refresh_list()

    def move_down(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current < len(items) - 1:
            items[current], items[current + 1] = items[current + 1], items[current]
            self.refresh_list()

    def clear_all(self) -> None:
        self.app._app_state["comparison_items"] = []
        self.refresh_list()

    def toggle_visibility(self, item_id: str, visible: bool) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.visible = visible
                break
        self._rerender()

    def update_color(self, item_id: str, color: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.color = color
                break
        self.refresh_list()

    def rename(self, item_id: str, new_name: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.label = f"{new_name}-第{item.segment_index + 1}段"
                item.file_name = new_name
                break
        self.refresh_list()

    def refresh_list(self) -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        list_data = [
            {
                "item_id": it.item_id,
                "display_name": it.file_name,
                "segment_label": f"-第{it.segment_index + 1}段",
                "color": it.color,
                "visible": it.visible,
            }
            for it in items
        ]
        if hasattr(app, "comparison_panel"):
            app.comparison_panel.set_items(list_data)
        self._update_summary()

    def _update_summary(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        table_data = []
        for item in items:
            if item.fit:
                table_data.append({
                    "alias": item.file_name,
                    "segment": item.segment_index + 1,
                    "slope": item.fit.slope_mv_per_dec,
                    "r2": item.fit.r2,
                    "n_points": item.fit.selected_count,
                })
        self.app.summary_table.set_items(table_data)

    def _rerender(self) -> None:
        if self.app._app_state.get("comparison_mode"):
            from gui.comparison import render_comparison
            render_comparison(self.app)
