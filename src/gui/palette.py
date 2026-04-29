"""调色板方案管理：颜色定义、方案持久化、管理器对话框。"""
from __future__ import annotations

import re
from pathlib import Path
from tkinter import colorchooser, messagebox
from typing import TYPE_CHECKING

try:
    import customtkinter as ctk
except ImportError:
    pass

from core.types import COMPARISON_COLORS
from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_LIGHT,
    BORDER_COLOR,
    CARD_BG,
    PROCESSED_TAG,
    SUCCESS,
    SUCCESS_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


def normalize_color_value(color: str | None) -> str | None:
    if not isinstance(color, str):
        return None
    text = color.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return None


def deserialize_segment_colors(app: TafelAnalyzerApp, raw: dict | None) -> dict[int, str]:
    colors: dict[int, str] = {}
    if not isinstance(raw, dict):
        return colors
    for key, value in raw.items():
        color = normalize_color_value(value)
        if color is None:
            continue
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            colors[index] = color
    return colors


def serialize_segment_colors(app: TafelAnalyzerApp, color_map: dict[int, str]) -> dict[str, str]:
    return {
        str(index): color
        for index, color in sorted(color_map.items())
        if normalize_color_value(color) is not None
    }


def normalize_palette_scheme_name(name: str | None) -> str:
    text = str(name or "").strip()
    return text or "默认方案"


def normalize_palette_schemes(
    app: TafelAnalyzerApp,
    raw: dict | None,
    legacy_palette: dict | None = None,
) -> dict[str, dict[int, str]]:
    schemes: dict[str, dict[int, str]] = {}
    if isinstance(raw, dict):
        for name, colors in raw.items():
            scheme_name = normalize_palette_scheme_name(name)
            normalized_colors = deserialize_segment_colors(app, colors)
            schemes[scheme_name] = normalized_colors
    legacy_colors = deserialize_segment_colors(app, legacy_palette)
    if legacy_colors:
        schemes.setdefault("默认方案", legacy_colors)
    if not schemes:
        schemes["默认方案"] = {}
    return schemes


def normalize_palette_scheme_slot_counts(
    app: TafelAnalyzerApp,
    raw: dict | None,
    schemes: dict[str, dict[int, str]],
) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if isinstance(raw, dict):
        for name, count in raw.items():
            scheme_name = normalize_palette_scheme_name(name)
            try:
                normalized[scheme_name] = max(0, int(count))
            except Exception:
                continue
    counts: dict[str, int] = {}
    for scheme_name, colors in schemes.items():
        highest = (max(colors.keys()) + 1) if colors else 0
        if scheme_name in normalized:
            counts[scheme_name] = max(normalized[scheme_name], highest)
        else:
            counts[scheme_name] = max(highest, 8)
    return counts


def palette_scheme_slot_count(app: TafelAnalyzerApp, scheme_name: str) -> int:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    counts = app._app_state.setdefault("palette_scheme_slot_counts", {})
    if scheme_name not in counts:
        colors = app._app_state.get("palette_schemes", {}).get(scheme_name, {})
        highest = (max(colors.keys()) + 1) if colors else 0
        counts[scheme_name] = max(highest, 8)
    return max(0, int(counts.get(scheme_name, 0)))


def set_palette_scheme_slot_count(app: TafelAnalyzerApp, scheme_name: str, count: int) -> int:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    colors = app._app_state.get("palette_schemes", {}).get(scheme_name, {})
    highest = (max(colors.keys()) + 1) if colors else 0
    normalized = max(highest, int(count))
    app._app_state.setdefault("palette_scheme_slot_counts", {})[scheme_name] = normalized
    return normalized


def get_palette_scheme_colors(app: TafelAnalyzerApp, scheme_name: str, *, include_defaults: bool = False) -> dict[int, str]:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    explicit_colors = dict(app._app_state.get("palette_schemes", {}).get(scheme_name, {}))
    if not include_defaults:
        return explicit_colors
    slot_count = palette_scheme_slot_count(app, scheme_name)
    return {
        index: explicit_colors.get(index, default_segment_color(index))
        for index in range(slot_count)
    }


def materialize_palette_scheme(app: TafelAnalyzerApp, scheme_name: str) -> dict[int, str]:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    colors = get_palette_scheme_colors(app, scheme_name, include_defaults=True)
    app._app_state.setdefault("palette_schemes", {})[scheme_name] = dict(colors)
    set_palette_scheme_slot_count(app, scheme_name, len(colors))
    return colors


def refresh_palette_scheme_options(app: TafelAnalyzerApp, preferred: str | None = None) -> None:
    from gui.widgets import set_option_values

    names = list(app._app_state.get("palette_schemes", {}).keys()) or ["默认方案"]
    active_name = normalize_palette_scheme_name(preferred or app._app_state.get("active_palette_scheme"))
    if active_name not in names:
        active_name = names[0]
    set_option_values(app.option_palette_scheme, names, active_name)
    set_option_values(app.option_compare_palette_scheme, names, active_name)
    app._app_state["active_palette_scheme"] = active_name


def get_active_palette_colors(app: TafelAnalyzerApp) -> dict[int, str]:
    scheme_name = normalize_palette_scheme_name(app._app_state.get("active_palette_scheme"))
    return get_palette_scheme_colors(app, scheme_name, include_defaults=True)


def set_active_palette_scheme(app: TafelAnalyzerApp, name: str | None, *, persist: bool = True) -> str:
    scheme_name = normalize_palette_scheme_name(name)
    schemes = app._app_state.setdefault("palette_schemes", {})
    if scheme_name not in schemes:
        schemes[scheme_name] = {}
    set_palette_scheme_slot_count(app, scheme_name, palette_scheme_slot_count(app, scheme_name))
    app._app_state["active_palette_scheme"] = scheme_name
    refresh_palette_scheme_options(app, preferred=scheme_name)
    if persist:
        _debounced_save_settings(app)
    return scheme_name


def default_segment_color(segment_index: int) -> str:
    return COMPARISON_COLORS[int(segment_index) % len(COMPARISON_COLORS)]


def merge_active_palette(app: TafelAnalyzerApp, color_map: dict[int, str], segment_count: int) -> dict[int, str]:
    merged = {
        int(index): color
        for index, color in color_map.items()
        if 0 <= int(index) < int(segment_count) and normalize_color_value(color) is not None
    }
    saved_palette = get_active_palette_colors(app)
    for index in range(int(segment_count)):
        if index not in merged:
            saved_color = normalize_color_value(saved_palette.get(index))
            if saved_color is not None:
                merged[index] = saved_color
    return merged


def text_color_for_fill(color: str) -> str:
    normalized = normalize_color_value(color)
    if normalized is None:
        return "#ffffff"
    red = int(normalized[1:3], 16)
    green = int(normalized[3:5], 16)
    blue = int(normalized[5:7], 16)
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return TEXT_PRIMARY if luminance >= 186 else "#ffffff"


def segment_color_map_for_path(app: TafelAnalyzerApp, path: Path) -> dict[int, str]:
    current_path = app._app_state.get("tdms_path")
    if current_path is not None and Path(current_path) == path:
        return dict(app._app_state.get("segment_colors", {}))
    cached_ui = app._app_state.get("file_ui_cache", {}).get(str(path), {})
    return deserialize_segment_colors(app, cached_ui.get("segment_colors", {}))


def _debounced_save_settings(app: TafelAnalyzerApp) -> None:
    """防抖保存设置：快速连续调用只会触发一次写入"""
    timer = app._app_state.get("_save_settings_timer")
    if timer is not None:
        app.after_cancel(timer)
    app._app_state["_save_settings_timer"] = app.after(1000, lambda: _do_save_settings(app))


def _do_save_settings(app: TafelAnalyzerApp) -> None:
    from gui import settings as s
    app._app_state["_save_settings_timer"] = None
    s.save_app_settings(app)


def set_palette_scheme_color(app: TafelAnalyzerApp, scheme_name: str, segment_index: int, color: str) -> None:
    normalized = normalize_color_value(color)
    if normalized is None:
        return
    scheme_name = set_active_palette_scheme(app, scheme_name, persist=False)
    app._app_state.setdefault("palette_schemes", {}).setdefault(scheme_name, {})[int(segment_index)] = normalized
    _debounced_save_settings(app)


def remove_palette_scheme_color(app: TafelAnalyzerApp, scheme_name: str, segment_index: int) -> None:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    schemes = app._app_state.setdefault("palette_schemes", {})
    colors = schemes.setdefault(scheme_name, {})
    colors.pop(int(segment_index), None)
    _debounced_save_settings(app)


def move_palette_scheme_color(app: TafelAnalyzerApp, scheme_name: str, from_idx: int, to_idx: int) -> None:
    scheme_name = normalize_palette_scheme_name(scheme_name)
    schemes = app._app_state.setdefault("palette_schemes", {})
    colors = schemes.setdefault(scheme_name, {})
    color_a = colors.get(from_idx)
    color_b = colors.get(to_idx)
    if color_a is not None:
        colors[to_idx] = color_a
    else:
        colors.pop(to_idx, None)
    if color_b is not None:
        colors[from_idx] = color_b
    else:
        colors.pop(from_idx, None)
    _debounced_save_settings(app)


def set_segment_color_for_path(app: TafelAnalyzerApp, path: Path, segment_index: int, color: str) -> None:
    normalized = normalize_color_value(color)
    if normalized is None:
        return
    current_path = app._app_state.get("tdms_path")
    if current_path is not None and Path(current_path) == path:
        app._app_state.setdefault("segment_colors", {})[int(segment_index)] = normalized
        app._save_current_file_ui_state()
        return
    file_key = str(path)
    cached_ui = dict(app._app_state.get("file_ui_cache", {}).get(file_key, {}))
    color_map = deserialize_segment_colors(app, cached_ui.get("segment_colors", {}))
    color_map[int(segment_index)] = normalized
    cached_ui["segment_colors"] = serialize_segment_colors(app, color_map)
    app._app_state["file_ui_cache"][file_key] = cached_ui


def get_segment_color(app: TafelAnalyzerApp, segment_index: int, *, file_path: Path | None = None) -> str:
    if file_path is None:
        color_map = app._app_state.get("segment_colors", {})
    else:
        color_map = segment_color_map_for_path(app, file_path)
    return color_map.get(int(segment_index), default_segment_color(segment_index))


def refresh_after_color_change(app: TafelAnalyzerApp) -> None:
    app.segments.refresh_buttons()
    app.comparison.refresh_list()
    if app._app_state.get("comparison_mode"):
        from gui import comparison as comp
        comp.render_comparison(app)
    elif app._app_state.get("prepared") is not None:
        from gui import rendering as r
        active_index = int(app._app_state.get("active_segment_index", 0))
        fit_error = app._app_state.get("fit_error_by_segment", {}).get(active_index)
        r.draw(app, app._app_state["prepared"], app._app_state["fit"], fit_error=fit_error)


def choose_segment_color(app: TafelAnalyzerApp, segment_index: int) -> None:
    current_color = get_segment_color(app, segment_index)
    chosen = colorchooser.askcolor(color=current_color, title=f"选择第{segment_index + 1}段颜色")[1]
    normalized = normalize_color_value(chosen)
    if normalized is None:
        return
    current_path = app._app_state.get("tdms_path")
    if current_path is None:
        return
    set_segment_color_for_path(app, current_path, segment_index, normalized)
    from gui import comparison as comp
    item_id = comp.comparison_item_id(current_path, segment_index)
    for item in app._app_state.get("comparison_items", []):
        if item.item_id == item_id:
            item.color = normalized
            break
    refresh_after_color_change(app)
    app.status_var.set(f"第{segment_index + 1}段颜色已更新 ✓")


def choose_comparison_color(app: TafelAnalyzerApp, item_id: str) -> None:
    for item in app._app_state.get("comparison_items", []):
        if item.item_id != item_id:
            continue
        chosen = colorchooser.askcolor(color=item.color, title=f"选择 {item.label} 的颜色")[1]
        normalized = normalize_color_value(chosen)
        if normalized is None:
            return
        item.color = normalized
        set_segment_color_for_path(app, item.file_path, item.segment_index, normalized)
        app.comparison.update_item_appearance(item)
        app.comparison.refresh_summary()
        app.segments.refresh_buttons()
        if app._app_state.get("comparison_mode"):
            from gui import comparison as comp
            comp.render_comparison(app)
        elif app._app_state.get("prepared") is not None:
            from gui import rendering as r
            active_index = int(app._app_state.get("active_segment_index", 0))
            fit_error = app._app_state.get("fit_error_by_segment", {}).get(active_index)
            r.draw(app, app._app_state["prepared"], app._app_state["fit"], fit_error=fit_error)
        app.status_var.set(f"{item.label} 颜色已更新 ✓")
        return


def apply_palette_scheme_to_current(app: TafelAnalyzerApp, show_message: bool = True) -> None:
    segments = app._app_state.get("segments", [])
    if not segments:
        if show_message:
            messagebox.showwarning("提示", "请先加载数据文件")
        return
    scheme_name = normalize_palette_scheme_name(app._app_state.get("active_palette_scheme"))
    schemes = app._app_state.get("palette_schemes", {})
    if scheme_name not in schemes:
        if show_message:
            messagebox.showwarning("提示", '配色方案"' + scheme_name + '"不存在')
        return
    set_active_palette_scheme(app, scheme_name, persist=False)
    saved_palette = get_active_palette_colors(app)
    if not saved_palette:
        if show_message:
            messagebox.showwarning("提示", '配色方案"' + scheme_name + '"还没有颜色定义')
        return
    app._app_state["segment_colors"] = {
        segment.index: saved_palette[segment.index]
        for segment in segments
        if segment.index in saved_palette
    }
    current_path = app._app_state.get("tdms_path")
    if current_path is not None:
        app._save_current_file_ui_state()
        from gui import comparison as comp
        item_lookup = {
            comp.comparison_item_id(current_path, item.segment_index): item
            for item in app._app_state.get("comparison_items", [])
            if item.file_path == current_path
        }
        for segment in segments:
            item = item_lookup.get(comp.comparison_item_id(current_path, segment.index))
            if item is not None:
                item.color = get_segment_color(app, segment.index)
    refresh_after_color_change(app)
    _debounced_save_settings(app)
    if show_message:
        app.status_var.set('已应用配色方案"' + scheme_name + '"（' + str(len(app._app_state["segment_colors"])) + " 段） ✓")


def apply_palette_scheme_to_comparison(app: TafelAnalyzerApp, show_message: bool = True) -> None:
    items = app._app_state.get("comparison_items", [])
    if not items:
        if show_message:
            messagebox.showwarning("提示", "当前没有对比项")
        return
    scheme_name = normalize_palette_scheme_name(app._app_state.get("active_palette_scheme"))
    schemes = app._app_state.get("palette_schemes", {})
    if scheme_name not in schemes:
        if show_message:
            messagebox.showwarning("提示", '配色方案"' + scheme_name + '"不存在')
        return
    palette = schemes.get(scheme_name, {})
    if not palette:
        if show_message:
            messagebox.showwarning("提示", '配色方案"' + scheme_name + '"还没有颜色定义')
        return
    color_list = [palette[i] for i in sorted(palette)]
    for position, item in enumerate(items):
        if color_list:
            item.color = color_list[position % len(color_list)]
        else:
            item.color = default_segment_color(position)
    app.comparison.refresh_list()
    if app._app_state.get("comparison_mode"):
        from gui import comparison as comp
        comp.render_comparison(app)
    _debounced_save_settings(app)
    if show_message:
        app.status_var.set('多文件对比已应用配色方案"' + scheme_name + '" ✓')


def open_palette_scheme_manager(app: TafelAnalyzerApp) -> None:
    existing = app._app_state.get("palette_manager_window")
    if existing is not None and existing.winfo_exists():
        existing.focus()
        existing.lift()
        return

    window = ctk.CTkToplevel(app)
    window.title("配色方案管理")
    window.geometry("860x620")
    window.minsize(760, 520)
    window.configure(fg_color=BG_LIGHT)
    window.transient(app)
    app._app_state["palette_manager_window"] = window

    manager_state: dict = {
        "selected_scheme": normalize_palette_scheme_name(app._app_state.get("active_palette_scheme")),
        "color_row_widgets": {},
        "scheme_buttons": {},
    }

    window.grid_columnconfigure(0, weight=0, minsize=220)
    window.grid_columnconfigure(1, weight=1)
    window.grid_rowconfigure(0, weight=1)

    left_panel = ctk.CTkFrame(window, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
    left_panel.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
    left_panel.grid_columnconfigure(0, weight=1)
    left_panel.grid_rowconfigure(2, weight=1)

    right_panel = ctk.CTkFrame(window, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
    right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
    right_panel.grid_columnconfigure(0, weight=1)
    right_panel.grid_rowconfigure(2, weight=1)

    ctk.CTkLabel(
        left_panel,
        text="配色方案",
        font=ctk.CTkFont(size=14, weight="bold"),
        text_color=TEXT_PRIMARY,
    ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

    create_row = ctk.CTkFrame(left_panel, fg_color="transparent")
    create_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
    create_row.grid_columnconfigure(0, weight=1)
    entry_new_scheme = ctk.CTkEntry(
        create_row,
        placeholder_text="输入新方案名",
        border_color=BORDER_COLOR,
        fg_color="#ffffff",
        text_color=TEXT_PRIMARY,
    )
    entry_new_scheme.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    btn_add_scheme = ctk.CTkButton(
        create_row,
        text="新增",
        width=60,
        fg_color=SUCCESS,
        hover_color=SUCCESS_HOVER,
        text_color="#ffffff",
        corner_radius=8,
    )
    btn_add_scheme.grid(row=0, column=1)

    scheme_list_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
    scheme_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
    scheme_list_frame.grid_columnconfigure(0, weight=1)

    btn_delete_scheme = ctk.CTkButton(
        left_panel,
        text="删除当前方案",
        fg_color="#fee2e2",
        hover_color="#fecaca",
        text_color="#dc2626",
        corner_radius=8,
        height=30,
    )
    btn_delete_scheme.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

    ctk.CTkLabel(
        right_panel,
        text="颜色设置",
        font=ctk.CTkFont(size=14, weight="bold"),
        text_color=TEXT_PRIMARY,
    ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
    manager_hint_var = ctk.StringVar(value="")
    ctk.CTkLabel(
        right_panel,
        textvariable=manager_hint_var,
        text_color=TEXT_SECONDARY,
        font=ctk.CTkFont(size=11),
        anchor="w",
    ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

    colors_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
    colors_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
    colors_frame.grid_columnconfigure(1, weight=1)
    colors_frame.grid_columnconfigure(2, weight=1)

    bottom_row = ctk.CTkFrame(right_panel, fg_color="transparent")
    bottom_row.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
    btn_add_color_slot = ctk.CTkButton(
        bottom_row,
        text="新增颜色位",
        fg_color="#e2e8f0",
        hover_color="#cbd5e1",
        text_color=TEXT_PRIMARY,
        corner_radius=8,
        height=30,
    )
    btn_add_color_slot.pack(side="left")

    def _selected_scheme_name() -> str:
        return normalize_palette_scheme_name(manager_state.get("selected_scheme"))

    def _scheme_slot_count(scheme_name: str) -> int:
        return palette_scheme_slot_count(app, scheme_name)

    def _render_color_rows() -> None:
        scheme_name = _selected_scheme_name()
        scheme_colors = get_palette_scheme_colors(app, scheme_name, include_defaults=True)
        manager_hint_var.set(f"当前方案：{scheme_name}")
        slot_count = _scheme_slot_count(scheme_name)

        row_widgets: dict[int, dict] = manager_state.setdefault("color_row_widgets", {})
        current_slots = set(row_widgets.keys())
        expected_slots = set(range(slot_count))

        # Remove slots that no longer exist
        for idx in sorted(current_slots - expected_slots):
            for w in row_widgets.pop(idx, {}).values():
                if w is not None:
                    w.destroy()

        # Update or create rows
        for row_idx in range(slot_count):
            color = scheme_colors.get(row_idx, default_segment_color(row_idx))

            if row_idx in row_widgets:
                _update_color_row(row_idx, color, row_widgets, slot_count)
            else:
                _create_color_row(row_idx, color, row_widgets)

        # Remove excess rows from tracking that were above slot_count
        for idx in sorted(current_slots - expected_slots):
            row_widgets.pop(idx, None)

    def _create_color_row(row_idx: int, color: str, row_widgets: dict) -> None:
        ctk.CTkLabel(
            colors_frame,
            text=f"第{row_idx + 1}段",
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=row_idx, column=0, sticky="w", padx=(2, 8), pady=4)

        preview_btn = ctk.CTkButton(
            colors_frame,
            text="",
            width=34,
            height=24,
            fg_color=color,
            hover_color=color,
            text_color=text_color_for_fill(color),
            corner_radius=6,
            command=lambda idx=row_idx: _pick_scheme_color(idx),
        )
        preview_btn.grid(row=row_idx, column=1, sticky="w", padx=(0, 6), pady=4)

        entry = ctk.CTkEntry(
            colors_frame,
            width=110,
            height=28,
            border_color=BORDER_COLOR,
            fg_color="#ffffff",
            text_color=TEXT_PRIMARY,
        )
        entry.grid(row=row_idx, column=2, sticky="ew", padx=(0, 6), pady=4)
        entry.insert(0, color)
        entry.bind(
            "<Return>",
            lambda _e, idx=row_idx, ent=entry: _apply_scheme_color_text(idx, ent.get()),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e, idx=row_idx, ent=entry: _apply_on_focusout(idx, ent),
        )

        apply_btn = ctk.CTkButton(
            colors_frame,
            text="应用",
            width=52,
            height=24,
            fg_color="#e2e8f0",
            hover_color="#cbd5e1",
            text_color=TEXT_PRIMARY,
            corner_radius=6,
            command=lambda idx=row_idx, ent=entry: _apply_scheme_color_text(idx, ent.get()),
        )
        apply_btn.grid(row=row_idx, column=3, sticky="w", padx=(0, 6), pady=4)

        delete_btn = ctk.CTkButton(
            colors_frame,
            text="删除",
            width=52,
            height=24,
            fg_color="#e2e8f0",
            hover_color="#cbd5e1",
            text_color=TEXT_PRIMARY,
            corner_radius=6,
            command=lambda idx=row_idx: _clear_scheme_color(idx),
        )
        delete_btn.grid(row=row_idx, column=4, sticky="w", pady=4)

        up_btn = None
        if row_idx > 0:
            up_btn = ctk.CTkButton(
                colors_frame,
                text="▲",
                width=30,
                height=24,
                fg_color="#e2e8f0",
                hover_color="#cbd5e1",
                text_color=TEXT_PRIMARY,
                corner_radius=6,
                command=lambda idx=row_idx: _swap_scheme_color(idx, idx - 1),
            )
            up_btn.grid(row=row_idx, column=5, sticky="w", padx=(4, 0), pady=4)

        down_btn = None
        if row_idx < (_scheme_slot_count(_selected_scheme_name()) - 1):
            down_btn = ctk.CTkButton(
                colors_frame,
                text="▼",
                width=30,
                height=24,
                fg_color="#e2e8f0",
                hover_color="#cbd5e1",
                text_color=TEXT_PRIMARY,
                corner_radius=6,
                command=lambda idx=row_idx: _swap_scheme_color(idx, idx + 1),
            )
            down_btn.grid(row=row_idx, column=6, sticky="w", padx=(2, 0), pady=4)

        row_widgets[row_idx] = {
            "preview_btn": preview_btn,
            "entry": entry,
            "apply_btn": apply_btn,
            "delete_btn": delete_btn,
            "up_btn": up_btn,
            "down_btn": down_btn,
        }

    def _update_color_row(row_idx: int, color: str, row_widgets: dict, slot_count: int) -> None:
        w = row_widgets[row_idx]
        w["preview_btn"].configure(
            fg_color=color, hover_color=color,
            text_color=text_color_for_fill(color),
        )
        if not _entry_has_focus(w["entry"]):
            w["entry"].delete(0, "end")
            w["entry"].insert(0, color)

        # Update up arrow
        if row_idx > 0:
            if w["up_btn"] is None:
                w["up_btn"] = ctk.CTkButton(
                    colors_frame, text="▲", width=30, height=24,
                    fg_color="#e2e8f0", hover_color="#cbd5e1",
                    text_color=TEXT_PRIMARY, corner_radius=6,
                    command=lambda idx=row_idx: _swap_scheme_color(idx, idx - 1),
                )
                w["up_btn"].grid(row=row_idx, column=5, sticky="w", padx=(4, 0), pady=4)
            else:
                w["up_btn"].grid()
        elif w["up_btn"] is not None:
            w["up_btn"].grid_remove()

        # Update down arrow
        if row_idx < slot_count - 1:
            if w["down_btn"] is None:
                w["down_btn"] = ctk.CTkButton(
                    colors_frame, text="▼", width=30, height=24,
                    fg_color="#e2e8f0", hover_color="#cbd5e1",
                    text_color=TEXT_PRIMARY, corner_radius=6,
                    command=lambda idx=row_idx: _swap_scheme_color(idx, idx + 1),
                )
                w["down_btn"].grid(row=row_idx, column=6, sticky="w", padx=(2, 0), pady=4)
            else:
                w["down_btn"].grid()
        elif w["down_btn"] is not None:
            w["down_btn"].grid_remove()

    def _entry_has_focus(entry: ctk.CTkEntry) -> bool:
        try:
            focused = entry.focus_get()
            return focused is not None and str(focused) == str(entry)
        except Exception:
            return False

    def _apply_on_focusout(segment_index: int, entry: ctk.CTkEntry) -> None:
        """Auto-apply color on FocusOut; silently revert invalid values."""
        value = entry.get().strip()
        normalized = normalize_color_value(value)
        if normalized is None:
            scheme_name = _selected_scheme_name()
            stored = get_palette_scheme_colors(app, scheme_name, include_defaults=True).get(
                segment_index, default_segment_color(segment_index)
            )
            entry.delete(0, "end")
            entry.insert(0, stored)
            return
        scheme_name = _selected_scheme_name()
        current = get_palette_scheme_colors(app, scheme_name, include_defaults=True).get(
            segment_index, ""
        )
        if normalized == normalize_color_value(current):
            return
        set_palette_scheme_color(app, scheme_name, segment_index, normalized)
        _sync_selected_scheme_to_current_views()
        _refresh_manager_views()

    def _swap_scheme_color(from_idx: int, to_idx: int) -> None:
        scheme_name = _selected_scheme_name()
        move_palette_scheme_color(app, scheme_name, from_idx, to_idx)
        _sync_selected_scheme_to_current_views()
        _refresh_manager_views()

    def _render_scheme_list() -> None:
        selected = _selected_scheme_name()
        scheme_names = list(app._app_state.get("palette_schemes", {}).keys())
        buttons = manager_state.setdefault("scheme_buttons", {})

        # Remove buttons for deleted schemes
        for name in set(buttons.keys()) - set(scheme_names):
            buttons.pop(name, None).destroy()

        # Update existing or create new
        for row_idx, scheme_name in enumerate(scheme_names):
            is_selected = scheme_name == selected
            if scheme_name in buttons:
                btn = buttons[scheme_name]
                btn.configure(
                    fg_color=ACCENT if is_selected else "#f8fafc",
                    hover_color=ACCENT_HOVER if is_selected else "#eef2ff",
                    text_color="#ffffff" if is_selected else TEXT_PRIMARY,
                )
                btn.grid(row=row_idx, column=0, sticky="ew", padx=2, pady=(0, 4))
            else:
                btn = ctk.CTkButton(
                    scheme_list_frame,
                    text=scheme_name,
                    anchor="w",
                    fg_color=ACCENT if is_selected else "#f8fafc",
                    hover_color=ACCENT_HOVER if is_selected else "#eef2ff",
                    text_color="#ffffff" if is_selected else TEXT_PRIMARY,
                    corner_radius=8,
                    command=lambda name=scheme_name: _select_manager_scheme(name),
                )
                btn.grid(row=row_idx, column=0, sticky="ew", padx=2, pady=(0, 4))
                buttons[scheme_name] = btn

    def _refresh_manager_views() -> None:
        _render_scheme_list()
        _render_color_rows()

    def _sync_selected_scheme_to_current_views() -> None:
        scheme_name = _selected_scheme_name()
        palette = get_palette_scheme_colors(app, scheme_name, include_defaults=True)

        segments = app._app_state.get("segments", [])
        if segments:
            app._app_state["segment_colors"] = {
                segment.index: palette[segment.index]
                for segment in segments
                if segment.index in palette
            }
            if app._app_state.get("tdms_path") is not None:
                app._save_current_file_ui_state()

        for item in app._app_state.get("comparison_items", []):
            item.color = palette.get(item.segment_index, default_segment_color(item.segment_index))

        if segments or app._app_state.get("comparison_items"):
            refresh_after_color_change(app)

    def _select_manager_scheme(scheme_name: str) -> None:
        manager_state["selected_scheme"] = set_active_palette_scheme(app, scheme_name, persist=False)
        _refresh_manager_views()

    def _pick_scheme_color(segment_index: int) -> None:
        scheme_name = _selected_scheme_name()
        current_color = get_palette_scheme_colors(app, scheme_name, include_defaults=True).get(
            segment_index,
            default_segment_color(segment_index),
        )
        chosen = colorchooser.askcolor(color=current_color, title=f"选择 {scheme_name} 第{segment_index + 1}段颜色")[1]
        normalized = normalize_color_value(chosen)
        if normalized is None:
            return
        set_palette_scheme_color(app, scheme_name, segment_index, normalized)
        _sync_selected_scheme_to_current_views()
        _refresh_manager_views()

    def _apply_scheme_color_text(segment_index: int, value: str) -> None:
        normalized = normalize_color_value(value)
        if normalized is None:
            messagebox.showwarning("提示", "请输入合法颜色，例如 #ffffff", parent=window)
            return
        scheme_name = _selected_scheme_name()
        set_palette_scheme_color(app, scheme_name, segment_index, normalized)
        _sync_selected_scheme_to_current_views()
        _refresh_manager_views()

    def _clear_scheme_color(segment_index: int) -> None:
        scheme_name = _selected_scheme_name()
        colors = app._app_state.setdefault("palette_schemes", {}).setdefault(scheme_name, {})
        shifted_colors = {}
        for idx, color_value in colors.items():
            numeric_idx = int(idx)
            if numeric_idx < segment_index:
                shifted_colors[numeric_idx] = color_value
            elif numeric_idx > segment_index:
                shifted_colors[numeric_idx - 1] = color_value
        app._app_state["palette_schemes"][scheme_name] = shifted_colors
        current_count = _scheme_slot_count(scheme_name)
        set_palette_scheme_slot_count(app, scheme_name, max(0, current_count - 1))
        _debounced_save_settings(app)
        _sync_selected_scheme_to_current_views()
        _refresh_manager_views()

    def _add_scheme() -> None:
        name = normalize_palette_scheme_name(entry_new_scheme.get())
        if name in app._app_state.get("palette_schemes", {}):
            messagebox.showwarning("提示", '配色方案"' + name + '"已存在', parent=window)
            return
        app._app_state.setdefault("palette_schemes", {})[name] = {}
        set_palette_scheme_slot_count(app, name, 8)
        materialize_palette_scheme(app, name)
        entry_new_scheme.delete(0, "end")
        manager_state["selected_scheme"] = set_active_palette_scheme(app, name, persist=False)
        _debounced_save_settings(app)
        _refresh_manager_views()

    def _delete_scheme() -> None:
        scheme_name = _selected_scheme_name()
        schemes = app._app_state.get("palette_schemes", {})
        if scheme_name not in schemes:
            return
        if len(schemes) <= 1:
            messagebox.showwarning("提示", "至少保留一套配色方案", parent=window)
            return
        if not messagebox.askyesno("删除方案", '确定删除配色方案"' + scheme_name + '"吗？', parent=window):
            return
        schemes.pop(scheme_name, None)
        app._app_state.setdefault("palette_scheme_slot_counts", {}).pop(scheme_name, None)
        next_name = next(iter(schemes.keys()))
        manager_state["selected_scheme"] = set_active_palette_scheme(app, next_name, persist=False)
        _sync_selected_scheme_to_current_views()
        _debounced_save_settings(app)
        _refresh_manager_views()

    def _add_color_slot() -> None:
        scheme_name = _selected_scheme_name()
        set_palette_scheme_slot_count(app, scheme_name, _scheme_slot_count(scheme_name) + 1)
        materialize_palette_scheme(app, scheme_name)
        _debounced_save_settings(app)
        _refresh_manager_views()

    def _close_palette_manager() -> None:
        app._app_state["palette_manager_window"] = None
        window.destroy()

    btn_add_scheme.configure(command=_add_scheme)
    btn_delete_scheme.configure(command=_delete_scheme)
    btn_add_color_slot.configure(command=_add_color_slot)
    entry_new_scheme.bind("<Return>", lambda _e: _add_scheme())
    window.protocol("WM_DELETE_WINDOW", _close_palette_manager)
    _refresh_manager_views()
