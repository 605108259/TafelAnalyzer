from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    ACTIVE_BTN_BG,
    ACTIVE_TEXT_COLOR,
    CHECKED_BG,
    CHECKED_HOVER_BG,
    INACTIVE_SELECTED_BG,
    INACTIVE_SELECTED_HOVER,
    INACTIVE_UNSELECTED_BG,
    INACTIVE_UNSELECTED_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    UNCHECKED_BG,
    UNCHECKED_HOVER_BG,
)
from gui import palette as p
from gui import rendering as r
from gui import settings

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


class SegmentPanel:
    def __init__(self, app: TafelAnalyzerApp):
        self.app = app

    def refresh_buttons(self) -> None:
        app = self.app
        selected_set = set(app._app_state.get("selected_segment_indices", []))
        active_index = int(app._app_state.get("active_segment_index", 0))
        segments = app._app_state.get("segments", [])
        existing_buttons = app._app_state.get("segment_item_buttons", {})
        existing_indices = set(existing_buttons.keys())
        expected_indices = {seg.index for seg in segments}

        def _colors(checked: bool, is_active: bool):
            cb_n = CHECKED_BG if checked else UNCHECKED_BG
            btn_n = ACTIVE_BTN_BG if is_active else (INACTIVE_SELECTED_BG if checked else INACTIVE_UNSELECTED_BG)
            cb_h = CHECKED_HOVER_BG if checked else UNCHECKED_HOVER_BG
            btn_h = ACCENT_HOVER if is_active else (INACTIVE_SELECTED_HOVER if checked else INACTIVE_UNSELECTED_HOVER)
            return cb_n, btn_n, cb_h, btn_h

        def _make_hover(cb, btn, cb_n, cb_h, btn_n, btn_h):
            def on_enter(_e):
                cb.configure(fg_color=cb_h)
                btn.configure(fg_color=btn_h)

            def on_leave(_e):
                cb.configure(fg_color=cb_n)
                btn.configure(fg_color=btn_n)
            return on_enter, on_leave

        def _apply_style(widgets: dict, segment, checked: bool, is_active: bool, curve_color: str,
                         cb_n, btn_n, cb_h, btn_h) -> dict:
            cb, seg_btn = widgets["cb"], widgets["btn"]
            cb.configure(
                text="☑" if checked else "☐",
                fg_color=cb_n,
                text_color=ACCENT if checked else TEXT_SECONDARY,
            )
            seg_btn.configure(
                text=("▶  " if is_active else "    ") + segment.label,
                fg_color=btn_n,
                text_color=ACTIVE_TEXT_COLOR if is_active else TEXT_PRIMARY,
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
            )
            widgets.get("color_btn").configure(
                fg_color=curve_color, hover_color=curve_color,
                text_color=p.text_color_for_fill(curve_color),
            )
            changed = (
                widgets.get("cb_hover") != cb_h or widgets.get("btn_hover") != btn_h
            )
            if changed:
                for w in (widgets["row"], cb, seg_btn, widgets["color_btn"]):
                    w.unbind("<Enter>")
                    w.unbind("<Leave>")
                on_enter, on_leave = _make_hover(cb, seg_btn, cb_n, cb_h, btn_n, btn_h)
                for w in (widgets["row"], cb, seg_btn, widgets["color_btn"]):
                    w.bind("<Enter>", on_enter, add="+")
                    w.bind("<Leave>", on_leave, add="+")
            else:
                on_enter, on_leave = widgets.get("on_enter"), widgets.get("on_leave")
            return {
                **widgets,
                "cb_normal": cb_n, "cb_hover": cb_h,
                "btn_normal": btn_n, "btn_hover": btn_h,
                "on_enter": on_enter, "on_leave": on_leave,
            }

        if existing_indices != expected_indices:
            for child in app.segment_scroll.winfo_children():
                child.destroy()
            app._app_state["segment_item_buttons"] = {}
            existing_buttons = {}
            for row_index, segment in enumerate(segments):
                checked = segment.index in selected_set
                is_active = segment.index == active_index
                curve_color = p.get_segment_color(app, segment.index)
                cb_n, btn_n, cb_h, btn_h = _colors(checked, is_active)

                row_frame = ctk.CTkFrame(app.segment_scroll, fg_color="transparent", height=32)
                row_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 2))
                row_frame.grid_columnconfigure(1, weight=1)

                cb = ctk.CTkButton(
                    row_frame, text="☑" if checked else "☐",
                    width=32, height=28, fg_color=cb_n, hover=False,
                    text_color=ACCENT if checked else TEXT_SECONDARY,
                    corner_radius=6, font=ctk.CTkFont(size=14),
                    command=lambda idx=segment.index: self.toggle_selected(idx),
                )
                cb.grid(row=0, column=0, padx=(0, 4))

                seg_btn = ctk.CTkButton(
                    row_frame, text=("▶  " if is_active else "    ") + segment.label,
                    anchor="w", fg_color=btn_n, hover=False,
                    text_color=ACTIVE_TEXT_COLOR if is_active else TEXT_PRIMARY,
                    height=28, corner_radius=6,
                    font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                    command=lambda idx=segment.index: self.set_active_segment(idx),
                )
                seg_btn.grid(row=0, column=1, sticky="ew")

                color_btn = ctk.CTkButton(
                    row_frame, text="", width=28, height=28,
                    fg_color=curve_color, hover_color=curve_color,
                    text_color=p.text_color_for_fill(curve_color),
                    corner_radius=6,
                    command=lambda idx=segment.index: p.choose_segment_color(app, idx),
                )
                color_btn.grid(row=0, column=2, padx=(4, 0))

                widgets = {"row": row_frame, "cb": cb, "btn": seg_btn, "color_btn": color_btn}
                app._app_state["segment_item_buttons"][segment.index] = _apply_style(
                    widgets, segment, checked, is_active, curve_color,
                    cb_n, btn_n, cb_h, btn_h,
                )
        else:
            for segment in segments:
                w = existing_buttons.get(segment.index)
                if w is None:
                    continue
                checked = segment.index in selected_set
                is_active = segment.index == active_index
                curve_color = p.get_segment_color(app, segment.index)
                cb_n, btn_n, cb_h, btn_h = _colors(checked, is_active)
                app._app_state["segment_item_buttons"][segment.index] = _apply_style(
                    w, segment, checked, is_active, curve_color,
                    cb_n, btn_n, cb_h, btn_h,
                )

    def set_active_segment(self, index: int) -> None:
        app = self.app
        app._app_state["active_segment_index"] = index
        self.refresh_buttons()
        app._save_current_file_ui_state()
        if app._app_state["_fitting_lock"]:
            app._app_state["_pending_gen"] = app._app_state["_op_generation"]
        else:
            app.fitting.restore_or_autorun()

    def set_selected_indices(self, indices: list[int], *, trigger_restore: bool = False) -> None:
        app = self.app
        n_segments = len(app._app_state.get("segments", []))
        unique = sorted({int(i) for i in indices if 0 <= int(i) < n_segments})
        app._app_state["selected_segment_indices"] = unique
        self.refresh_buttons()
        app._save_current_file_ui_state()
        if trigger_restore and app._app_state.get("channels") is not None:
            if app._app_state["_fitting_lock"]:
                app._app_state["_pending_gen"] = app._app_state["_op_generation"]
            else:
                app.fitting.restore_or_autorun()

    def toggle_selected(self, index: int) -> None:
        current = set(self.app._app_state.get("selected_segment_indices", []))
        if index in current:
            current.remove(index)
        else:
            current.add(index)
        self.set_selected_indices(sorted(current), trigger_restore=True)

    def select_all(self) -> None:
        self.set_selected_indices(
            [seg.index for seg in self.app._app_state.get("segments", [])],
            trigger_restore=True,
        )

    def clear_all(self) -> None:
        self.set_selected_indices([], trigger_restore=True)
