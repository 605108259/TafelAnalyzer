from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from ui.activity_bar import PANEL_COMPARISON, PANEL_FILES, PANEL_PALETTE, PANEL_HISTORY
from core.types import COMPARISON_COLORS

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


class ViewCoordinator:
    """Centralizes UI refresh and chart mode transitions.

    Controllers mutate state, then call this coordinator. Keeping view refresh
    here avoids scattered "remember to redraw X" calls after every state change.
    """

    def __init__(self, app: TafelAnalyzerApp):
        self.app = app
        self._render_token = 0

    def show_panel(self, panel_id: int) -> None:
        app = self.app
        if panel_id < 0:
            app.side_stack.hide()
            return
        app.side_stack.show()
        app.side_stack.setCurrentIndex(panel_id)

        if panel_id == PANEL_FILES:
            self.show_single()
        elif panel_id == PANEL_COMPARISON:
            self.show_comparison()
        elif panel_id == PANEL_PALETTE:
            self.show_palette()
        elif panel_id == PANEL_HISTORY:
            self.show_history()

    def show_single(self) -> None:
        app = self.app
        from core.rendering import persist_current_plot_view_state
        previous_mode = app._app_state.get("active_chart_mode")
        persist_current_plot_view_state(app)
        if previous_mode != "single" and hasattr(app.chart, "_nav_toolbar"):
            app.chart._nav_toolbar.update()
        app.state.set_comparison_mode(False)
        if hasattr(app, "_set_comp_nav_active"):
            app._set_comp_nav_active(None)
        app.right_stack.setCurrentIndex(0)
        app.toolbar.show()
        app._comp_nav.hide()
        app.summary_table.hide()
        # 若模式未变化，只做轻量刷新（draw_idle），避免全量重绘 axes
        if previous_mode == "single":
            return
        self._queue_chart_render("single")

    def show_comparison(self) -> None:
        app = self.app
        from core.rendering import persist_current_plot_view_state
        previous_mode = app._app_state.get("active_chart_mode")
        persist_current_plot_view_state(app)
        if previous_mode != "comparison" and hasattr(app.chart, "_nav_toolbar"):
            app.chart._nav_toolbar.update()
        app.state.set_comparison_mode(True)
        app.right_stack.setCurrentIndex(0)
        app.toolbar.hide()
        app._comp_nav.show()
        app.summary_table.hide()
        # 若模式未变化，只做轻量刷新（draw_idle），避免全量重绘 axes
        if previous_mode == "comparison":
            return
        self._queue_chart_render("comparison")

    def _queue_chart_render(self, mode: str) -> None:
        self._render_token += 1
        token = self._render_token

        def render_if_current() -> None:
            if token != self._render_token:
                return
            if mode == "single":
                if self.app.state.comparison_mode:
                    return
                self.render_single()
                return
            if not self.app.state.comparison_mode:
                return
            self.render_comparison()

        QTimer.singleShot(0, render_if_current)

    def show_palette(self) -> None:
        app = self.app
        self._render_token += 1
        app.right_stack.setCurrentWidget(app.palette_workspace)
        app.summary_table.hide()
        self.refresh_palette_workspace()

    def show_history(self) -> None:
        app = self.app
        self._render_token += 1
        app.right_stack.setCurrentWidget(app.history_workspace)
        app.toolbar.hide()
        app._comp_nav.hide()
        app.summary_table.hide()
        self.refresh_history_panel()

    def render_single(self) -> None:
        app = self.app
        prepared = app.state.analysis.prepared
        if prepared is None:
            from core.rendering import draw_placeholder
            draw_placeholder(app)
            return
        from core.rendering import draw
        draw(app, prepared, app.state.analysis.fit)

    def render_comparison(self) -> None:
        from core.comparison import render_comparison
        render_comparison(self.app)

    def render_active_chart(self) -> None:
        if self.app.state.comparison_mode:
            self.render_comparison()
        else:
            self.render_single()

    def reset_active_segment(self) -> None:
        """重置激活分段为无选中状态。"""
        app = self.app
        if app.state.comparison_mode:
            app.state.comparison.set_highlight(-1)
            self.refresh_comparison_list(rebuild=False)
            self.render_comparison()
        else:
            app.state.segments.set_active(-1)
            self.refresh_segments()
            self.render_single()

    def refresh_file_list(self) -> None:
        app = self.app
        app.file_segment_panel.set_file_paths(
            app.state.files.selected_paths,
            processed=set(app._app_state.get("current_result_keys", {}).keys()),
            names=app.state.files.display_names(),
        )

    def refresh_history_panel(self) -> None:
        app = self.app
        if hasattr(app, "history_panel"):
            changed = app.history_panel.set_entries(app._app_state.get("project_history", []))
            if changed and hasattr(app, "history_workspace"):
                app.history_workspace.set_entry(app.history_panel.current_entry())

    def refresh_segments(self, *, rebuild: bool = False) -> None:
        app = self.app
        segments = app.state.analysis.segments
        kwargs = {
            "active_index": app.state.segments.active_index,
            "checked_indices": set(app.state.segments.selected_indices),
            "colors": app._app_state.get("segment_colors", {}),
            "fit_by_segment": app.state.analysis.fit_by_segment,
        }
        if rebuild:
            app.file_segment_panel.set_segments(segments, **kwargs)
        else:
            app.file_segment_panel.update_segment_state(**kwargs)

    def refresh_comparison_list(self, *, rebuild: bool = True) -> None:
        app = self.app
        if not hasattr(app, "comparison_panel"):
            return
        highlight_row = app.state.comparison.highlight_row
        if rebuild:
            app.comparison_panel.set_items(
                app.state.comparison.item_data(),
                highlighted_row=highlight_row,
            )
        else:
            app.comparison_panel.set_highlighted(highlight_row)

    def update_comparison_name(self, item_id: str, display_name: str, segment_label: str = "") -> None:
        if hasattr(self.app, "comparison_panel"):
            self.app.comparison_panel.update_item_name(item_id, display_name, segment_label)

    def refresh_palette_controls(self) -> None:
        app = self.app
        app.state.palette.ensure_default()
        schemes = app.state.palette.scheme_names()
        active = app.state.palette.active_name
        if hasattr(app, "file_segment_panel"):
            app.file_segment_panel.set_palette_schemes(schemes, active)
        if hasattr(app, "comparison_panel"):
            app.comparison_panel.set_palette_schemes(schemes, active)
        if hasattr(app, "palette_sidebar"):
            self.refresh_palette_sidebar()
        if hasattr(app, "palette_workspace"):
            self.refresh_palette_workspace()

    def refresh_palette_sidebar(self) -> None:
        app = self.app
        schemes = app.state.palette.scheme_names()
        active = app.state.palette.active_name
        colors = app.state.palette.colors(active)
        names = [str(index + 1) for index in range(len(colors))]
        app.palette_sidebar.set_schemes(schemes, active)
        app.palette_sidebar.set_colors(colors, names)
        app.palette_sidebar.count_combo.blockSignals(True)
        app.palette_sidebar.count_combo.setCurrentText(str(len(colors)))
        app.palette_sidebar.count_combo.blockSignals(False)

    def refresh_palette_workspace(self) -> None:
        app = self.app
        scheme_name = app.state.palette.active_name
        colors = app.state.palette.colors(scheme_name)
        names = [str(index + 1) for index in range(len(colors))]
        app.palette_workspace.set_scheme(scheme_name, colors, names)

    def current_segment_color(self, segment_index: int) -> str:
        return self.app._app_state.get("segment_colors", {}).get(
            int(segment_index),
            COMPARISON_COLORS[int(segment_index) % len(COMPARISON_COLORS)],
        )
