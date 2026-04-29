from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.theme import (
    ACCENT,
    BORDER_COLOR,
    CARD_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from gui import palette as p
from gui import comparison as comp
from core.types import COMPARISON_COLORS, ComparisonItem

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


class ComparisonManager:
    def __init__(self, app: TafelAnalyzerApp):
        self.app = app

    def update_count_badge(self) -> None:
        n = len(self.app._app_state["comparison_items"])
        if n > 0:
            self.app.compare_count_var.set(f"📊  跨文件对比 ({n})")
        else:
            self.app.compare_count_var.set("📊  跨文件对比")

    def add_from_current(self) -> None:
        app = self.app
        if app._app_state["tdms_path"] is None:
            messagebox.showwarning("提示", "请先选择并加载数据文件")
            return
        selected_indices = list(app._app_state.get("selected_segment_indices", []))
        if not selected_indices:
            messagebox.showwarning("提示", "请先勾选要添加的分段")
            return
        tdms_path = app._app_state["tdms_path"]
        prepared_map = app._app_state.get("prepared_by_segment", {})
        fit_map = app._app_state.get("fit_by_segment", {})
        existing_ids = {item.item_id: idx for idx, item in enumerate(app._app_state["comparison_items"])}
        added, updated = 0, 0
        for seg_idx in selected_indices:
            prepared = prepared_map.get(seg_idx)
            if prepared is None:
                continue
            fit = fit_map.get(seg_idx)
            item_id = comp.comparison_item_id(tdms_path, seg_idx)
            color = p.get_segment_color(app, seg_idx)
            new_item = ComparisonItem(
                item_id=item_id, file_path=tdms_path, file_name=tdms_path.name,
                segment_index=seg_idx, prepared=prepared, fit=fit,
                label=f"{tdms_path.stem} | 第{seg_idx + 1}段", color=color,
            )
            if item_id in existing_ids:
                old = app._app_state["comparison_items"][existing_ids[item_id]]
                new_item = ComparisonItem(
                    item_id=item_id, file_path=tdms_path, file_name=tdms_path.name,
                    segment_index=seg_idx, prepared=prepared, fit=fit,
                    label=old.label, color=old.color,
                )
                app._app_state["comparison_items"][existing_ids[item_id]] = new_item
                updated += 1
            else:
                app._app_state["comparison_items"].append(new_item)
                existing_ids[item_id] = len(app._app_state["comparison_items"]) - 1
                added += 1
        self.update_count_badge()
        self.refresh_list()
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)
        parts = []
        if added:
            parts.append(f"添加 {added} 项")
        if updated:
            parts.append(f"更新 {updated} 项")
        app.status_var.set(f"对比列表：{'、'.join(parts)} ✓" if parts else "没有可添加的已处理分段")

    def add_all_processed(self) -> None:
        app = self.app
        added = 0
        existing_ids = {item.item_id for item in app._app_state["comparison_items"]}
        for file_key, cache_key in app._app_state["current_result_keys"].items():
            cached = app._app_state["result_cache"].get(cache_key)
            if cached is None:
                continue
            file_path = Path(file_key)
            for seg_idx in cached.get("selected_segment_indices", []):
                item_id = comp.comparison_item_id(file_path, seg_idx)
                if item_id in existing_ids:
                    continue
                prepared = cached.get("prepared_by_segment", {}).get(seg_idx)
                fit = cached.get("fit_by_segment", {}).get(seg_idx)
                if prepared is None:
                    continue
                n = len(app._app_state["comparison_items"])
                color_map = p.segment_color_map_for_path(app, file_path)
                app._app_state["comparison_items"].append(ComparisonItem(
                    item_id=item_id, file_path=file_path, file_name=file_path.name,
                    segment_index=seg_idx, prepared=prepared, fit=fit,
                    label=f"{file_path.stem} | 第{seg_idx + 1}段",
                    color=color_map.get(seg_idx, COMPARISON_COLORS[n % len(COMPARISON_COLORS)]),
                ))
                existing_ids.add(item_id)
                added += 1
        self.update_count_badge()
        self.refresh_list()
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)
        app.status_var.set(f"已添加 {added} 个对比项 ✓" if added > 0 else "没有新的已处理段可添加")

    def remove_item(self, item_id: str) -> None:
        app = self.app
        app._app_state["comparison_items"] = [item for item in app._app_state["comparison_items"] if item.item_id != item_id]
        existing = app._app_state["comparison_item_widgets"]
        if item_id in existing:
            existing[item_id]["frame"].destroy()
            del existing[item_id]
        for row_idx, item in enumerate(app._app_state["comparison_items"]):
            if item.item_id in existing:
                existing[item.item_id]["frame"].grid(row=row_idx, column=0)
        self.update_count_badge()
        self.refresh_summary()
        if not app._app_state["comparison_items"]:
            app.compare_empty_label.grid(row=0, column=0, pady=40)
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)

    def toggle_visibility(self, item_id: str) -> None:
        app = self.app
        for item in app._app_state["comparison_items"]:
            if item.item_id == item_id:
                new_item = ComparisonItem(
                    item_id=item.item_id, file_path=item.file_path,
                    file_name=item.file_name, segment_index=item.segment_index,
                    prepared=item.prepared, fit=item.fit, label=item.label,
                    color=item.color, visible=not item.visible,
                )
                break
        else:
            return
        for idx, it in enumerate(app._app_state["comparison_items"]):
            if it.item_id == item_id:
                app._app_state["comparison_items"][idx] = new_item
                break
        self.update_item_appearance(new_item)
        self.refresh_summary()
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)

    def update_label(self, item_id: str, new_label: str) -> None:
        app = self.app
        for idx, item in enumerate(app._app_state["comparison_items"]):
            if item.item_id == item_id:
                stripped = new_label.strip()
                if stripped and stripped != item.label:
                    updated = ComparisonItem(
                        item_id=item.item_id, file_path=item.file_path,
                        file_name=item.file_name, segment_index=item.segment_index,
                        prepared=item.prepared, fit=item.fit, label=stripped,
                        color=item.color, visible=item.visible,
                    )
                    app._app_state["comparison_items"][idx] = updated
                    self.update_item_appearance(updated)
                break
        self.refresh_summary()
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)

    def clear_all(self) -> None:
        app = self.app
        app._app_state["comparison_items"].clear()
        for widget_dict in app._app_state["comparison_item_widgets"].values():
            widget_dict["frame"].destroy()
        app._app_state["comparison_item_widgets"].clear()
        self.update_count_badge()
        app.compare_empty_label.grid(row=0, column=0, pady=40)
        app._set_compare_result("暂无对比项")
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)

    def make_item_widgets(self, item, row_idx: int) -> dict:
        app = self.app
        card = ctk.CTkFrame(
            app.compare_list_frame,
            fg_color="#f8fafc" if item.visible else "#f1f5f9",
            corner_radius=10, border_width=1,
            border_color=item.color if item.visible else BORDER_COLOR,
        )
        card.grid(row=row_idx, column=0, sticky="ew", pady=(0, 4))
        card.grid_columnconfigure(1, weight=1)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(6, 2))
        top_row.grid_columnconfigure(1, weight=1)
        dot = ctk.CTkLabel(
            top_row, text="●", text_color=item.color if item.visible else "#94a3b8",
            font=ctk.CTkFont(size=16), width=20,
        )
        dot.grid(row=0, column=0, padx=(0, 6))
        slope_text = f"{item.fit.slope_mv_per_dec:.1f} mV/dec" if item.fit else "未拟合"
        info = ctk.CTkLabel(
            top_row,
            text=f"{item.file_name} | 第{item.segment_index + 1}段 | {slope_text}",
            text_color=TEXT_PRIMARY if item.visible else TEXT_SECONDARY,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        info.grid(row=0, column=1, sticky="ew")

        label_entry = ctk.CTkEntry(
            card, height=26, border_color=BORDER_COLOR, fg_color="#ffffff",
            text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=11),
            placeholder_text="自定义标签…",
        )
        label_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 4))
        label_entry.insert(0, item.label)
        captured_id = item.item_id
        label_entry.bind(
            "<FocusOut>",
            lambda _e, _id=captured_id, _ent=label_entry: self.update_label(_id, _ent.get()),
        )
        label_entry.bind(
            "<Return>",
            lambda _e, _id=captured_id, _ent=label_entry: self.update_label(_id, _ent.get()),
        )

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 6))
        vis_btn = ctk.CTkButton(
            btn_row, text="👁" if item.visible else "👁‍🗨",
            width=40, height=24, fg_color="#e2e8f0", hover_color="#cbd5e1",
            text_color=TEXT_PRIMARY, corner_radius=6,
            command=lambda _id=captured_id: self.toggle_visibility(_id),
        )
        vis_btn.pack(side="left", padx=(0, 4))
        color_btn = ctk.CTkButton(
            btn_row, text="", width=24, height=24,
            fg_color=item.color, hover_color=item.color,
            text_color=p.text_color_for_fill(item.color), corner_radius=6,
            command=lambda _id=captured_id: p.choose_comparison_color(app, _id),
        )
        color_btn.pack(side="left", padx=(0, 4))
        del_btn = ctk.CTkButton(
            btn_row, text="🗑", width=40, height=24,
            fg_color="#fee2e2", hover_color="#fecaca",
            text_color="#dc2626", corner_radius=6,
            command=lambda _id=captured_id: self.remove_item(_id),
        )
        del_btn.pack(side="left")

        return {"frame": card, "dot": dot, "info": info, "entry": label_entry,
                "vis_btn": vis_btn, "color_btn": color_btn, "del_btn": del_btn}

    def update_item_appearance(self, item) -> None:
        app = self.app
        widgets = app._app_state["comparison_item_widgets"].get(item.item_id)
        if widgets is None:
            return
        card = widgets["frame"]
        card.configure(
            fg_color="#f8fafc" if item.visible else "#f1f5f9",
            border_color=item.color if item.visible else BORDER_COLOR,
        )
        widgets["dot"].configure(text_color=item.color if item.visible else "#94a3b8")
        slope_text = f"{item.fit.slope_mv_per_dec:.1f} mV/dec" if item.fit else "未拟合"
        widgets["info"].configure(
            text=f"{item.file_name} | 第{item.segment_index + 1}段 | {slope_text}",
            text_color=TEXT_PRIMARY if item.visible else TEXT_SECONDARY,
        )
        widgets["vis_btn"].configure(text="👁" if item.visible else "👁‍🗨")
        widgets["color_btn"].configure(
            fg_color=item.color, hover_color=item.color,
            text_color=p.text_color_for_fill(item.color),
        )
        if str(widgets["entry"].cget("state")) != "disabled":
            try:
                has_focus = widgets["entry"].focus_get() == widgets["entry"]
            except Exception:
                has_focus = False
            if not has_focus:
                widgets["entry"].delete(0, "end")
                widgets["entry"].insert(0, item.label)

    def refresh_summary(self) -> None:
        app = self.app
        items = app._app_state["comparison_items"]
        lines = [f"共 {len(items)} 项对比（{sum(1 for i in items if i.visible)} 项显示中）", ""]
        lines.append(f"{'标签':<20} {'slope':>12} {'R²':>10}")
        lines.append("─" * 46)
        for item in items:
            if item.fit:
                lines.append(f"{item.label:<20} {item.fit.slope_mv_per_dec:>10.2f}  {item.fit.r2:>10.6f}")
            else:
                lines.append(f"{item.label:<20} {'未拟合':>10}  {'—':>10}")
        app._set_compare_result("\n".join(lines))

    def refresh_list(self) -> None:
        app = self.app
        items = app._app_state["comparison_items"]
        existing_widgets = app._app_state["comparison_item_widgets"]
        current_ids = {item.item_id for item in items}

        for removed_id in set(existing_widgets) - current_ids:
            existing_widgets[removed_id]["frame"].destroy()
            del existing_widgets[removed_id]

        if not items:
            app.compare_empty_label.grid(row=0, column=0, pady=40)
            app._set_compare_result("暂无对比项")
            return
        app.compare_empty_label.grid_remove()

        for row_idx, item in enumerate(items):
            if item.item_id in existing_widgets:
                self.update_item_appearance(item)
            else:
                existing_widgets[item.item_id] = self.make_item_widgets(item, row_idx)
            existing_widgets[item.item_id]["frame"].grid(row=row_idx, column=0)

        self.refresh_summary()
