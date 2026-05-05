from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from core.types import ComparisonItem, COMPARISON_COLORS
from gui_qt.controllers.base import BaseAppController
from gui import comparison as comp

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class ComparisonController(BaseAppController):
    """Manages comparison items CRUD and rendering."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)

    def add_from_current(self) -> None:
        """Add all checked segments from the current file to comparison."""
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        checked = set(app._app_state.get("selected_segment_indices", []))
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        if not checked:
            QMessageBox.warning(app, "提示", "请先勾选要对比的分段")
            return
        alias = (
            app._app_state.get("file_ui_cache", {}).get(str(path), {}).get("file_alias")
            or path.stem
        )
        items = app._app_state.setdefault("comparison_items", [])
        added = 0
        for seg_idx in sorted(checked):
            seg_prepared = prepared_by.get(seg_idx)
            if seg_prepared is None:
                continue
            item_id = comp.comparison_item_id(path, seg_idx)
            if any(it.item_id == item_id for it in items):
                continue
            color = app._app_state.get("segment_colors", {}).get(
                int(seg_idx),
                COMPARISON_COLORS[int(seg_idx) % len(COMPARISON_COLORS)],
            )
            items.append(ComparisonItem(
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
            added += 1
        if added == 0:
            QMessageBox.warning(app, "提示", "勾选的分段已在对比列表中")
            return
        self.refresh_list()

    def add_all_processed(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        items = app._app_state.setdefault("comparison_items", [])
        alias = (
            app._app_state.get("file_ui_cache", {}).get(str(path), {}).get("file_alias")
            or path.stem
        )

        for seg_idx in prepared_by:
            item_id = comp.comparison_item_id(path, seg_idx)
            if any(it.item_id == item_id for it in items):
                continue
            color = app._app_state.get("segment_colors", {}).get(
                int(seg_idx),
                COMPARISON_COLORS[int(seg_idx) % len(COMPARISON_COLORS)],
            )
            items.append(ComparisonItem(
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
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if 0 <= current < len(items):
            items.pop(current)
            self.refresh_list()

    def remove_by_id(self, item_id: str) -> None:
        items = self.app._app_state.get("comparison_items", [])
        self.app._app_state["comparison_items"] = [it for it in items if it.item_id != item_id]
        self.refresh_list()

    def highlight_item(self, row: int) -> None:
        self.app._app_state["comparison_highlight_row"] = row
        self._rerender()

    def move_up(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current > 0:
            items[current], items[current - 1] = items[current - 1], items[current]
            self.refresh_list()
            self.app.comparison_panel.item_list.setCurrentRow(current - 1)

    def move_down(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current < len(items) - 1:
            items[current], items[current + 1] = items[current + 1], items[current]
            self.refresh_list()
            self.app.comparison_panel.item_list.setCurrentRow(current + 1)

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
        # Restore selection to the renamed item
        for i, it in enumerate(self.app._app_state.get("comparison_items", [])):
            if it.item_id == item_id:
                self.app.comparison_panel.item_list.setCurrentRow(i)
                break

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
        # Summary table removed from comparison view; kept for export only.
        pass

    def _rerender(self) -> None:
        if self.app._app_state.get("comparison_mode"):
            from gui.comparison import render_comparison
            render_comparison(self.app)
