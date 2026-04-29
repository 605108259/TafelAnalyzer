"""Tooltip for CTk widgets — Leave-driven hide with polling backup.

CTkButton draws text/icons on _text_label layered above _canvas, so events
are bound on both.  The pattern:

  Enter  → schedule show after 400 ms (avoids flicker on quick passes)
  Leave  → schedule hide after 100 ms (absorb sub-widget transitions)
  Poll   → every 500 ms check pointer position; hide if outside (safety net)

The polling safety net catches the case where Leave is dropped during fast
mouse movement.  Normal hovering (stationary) is handled by Leave.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

SHOW_DELAY_MS = 400
LEAVE_DELAY_MS = 100  # brief delay to absorb _canvas ↔ _text_label transitions
POLL_INTERVAL_MS = 500


class ToolTip:
    """Floating tooltip with polling safety net."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self._show_id = None
        self._leave_id = None
        self._poll_id = None

        bound = False
        for attr in ("_canvas", "_text_label"):
            target = getattr(widget, attr, None)
            if target is not None:
                target.bind("<Enter>", self._on_enter, add="+")
                target.bind("<Leave>", self._on_leave, add="+")
                bound = True
        if not bound:
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")

    # ── tk event handlers ────────────────────────────────────────────

    def _on_enter(self, _event=None) -> None:
        self._cancel_show()
        self._cancel_leave()
        if self.tip_window is not None:
            # Already visible (transition between _canvas ↔ _text_label).
            # Restart the polling safety net.
            self._start_poll()
            return
        self._stop_poll()
        self._show_id = self.widget.after(SHOW_DELAY_MS, self._show)

    def _on_leave(self, _event=None) -> None:
        self._cancel_show()
        self._cancel_leave()
        if self.tip_window is not None:
            # Brief delay so Enter on the sibling sub-widget can cancel it.
            self._leave_id = self.widget.after(LEAVE_DELAY_MS, self._start_poll)

    # ── show ─────────────────────────────────────────────────────────

    def _show(self) -> None:
        self._show_id = None
        if self.tip_window is not None:
            return
        w = self.widget
        x = w.winfo_rootx() + w.winfo_width() // 2
        y = w.winfo_rooty() + w.winfo_height() + 4

        tw = tk.Toplevel(w)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tw.configure(bg="#ffffff")

        ctk.CTkLabel(
            tw,
            text=self.text,
            fg_color="#ffffff",
            text_color="#1e293b",
            corner_radius=6,
            font=ctk.CTkFont(size=11),
        ).pack(padx=8, pady=3)
        self.tip_window = tw
        self._start_poll()

    # ── hide ─────────────────────────────────────────────────────────

    def _hide(self) -> None:
        self._cancel_show()
        self._cancel_leave()
        self._stop_poll()
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None

    # ── polling safety net ───────────────────────────────────────────

    def _start_poll(self) -> None:
        self._stop_poll()
        self._poll_id = self.widget.after(POLL_INTERVAL_MS, self._poll)

    def _poll(self) -> None:
        if self.tip_window is None:
            return
        w = self.widget
        try:
            x, y = w.winfo_pointerxy()
            wx, wy = w.winfo_rootx(), w.winfo_rooty()
            inside = wx <= x <= wx + w.winfo_width() and wy <= y <= wy + w.winfo_height()
        except Exception:
            inside = False
        if inside:
            self._poll_id = w.after(POLL_INTERVAL_MS, self._poll)
        else:
            self._hide()

    def _stop_poll(self) -> None:
        if self._poll_id is not None:
            try:
                self.widget.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None

    # ── internal cleanup ─────────────────────────────────────────────

    def _cancel_show(self) -> None:
        if self._show_id is not None:
            try:
                self.widget.after_cancel(self._show_id)
            except Exception:
                pass
            self._show_id = None

    def _cancel_leave(self) -> None:
        if self._leave_id is not None:
            try:
                self.widget.after_cancel(self._leave_id)
            except Exception:
                pass
            self._leave_id = None
