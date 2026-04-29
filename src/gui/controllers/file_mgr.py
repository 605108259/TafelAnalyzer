from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from tkinter import filedialog, messagebox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import CURRENT_PREFERRED_NAMES, POTENTIAL_PREFERRED_NAMES, ComparisonItem
from core.utils import pick_channel_name
from gui.theme import PROCESSED_TAG
from gui.widgets import path_labels, set_combo_values, set_entry_text, parse_segment_selection
from gui.serialization import fit_from_dict, prepared_from_dict
from gui import settings
from gui import palette as p
from gui import rendering as r
from gui import cache as c
from gui import comparison as comp
from gui.logger import log_info, log_error, log_warning

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


class FileManager:
    def __init__(self, app: TafelAnalyzerApp):
        self.app = app

    def refresh_file_choices(self, preferred_path: Path | None = None) -> None:
        app = self.app
        base_lookup = path_labels(app._app_state["selected_paths"])
        decorated_lookup: dict[str, Path] = {}
        preferred_label: str | None = None
        for base_label, path in base_lookup.items():
            label = base_label
            if str(path) in app._app_state["current_result_keys"]:
                label = f"{base_label} | {PROCESSED_TAG}"
            decorated_lookup[label] = path
            if preferred_path is not None and path == preferred_path:
                preferred_label = label
        app._app_state["path_lookup"] = decorated_lookup
        if decorated_lookup:
            set_combo_values(app.combo_file, list(decorated_lookup.keys()), preferred_label)
        else:
            set_combo_values(app.combo_file, [""], None)
        processed_count = sum(
            1 for path in app._app_state["selected_paths"]
            if str(path) in app._app_state["current_result_keys"]
        )
        if app._app_state["selected_paths"]:
            app.file_info_var.set(f"已选择 {len(app._app_state['selected_paths'])} 个文件，已处理 {processed_count} 个")
        else:
            app.file_info_var.set("未选择文件")

    def switch_file(self) -> None:
        app = self.app
        label = app.combo_file.get().strip()
        if not label:
            return
        app._save_current_file_ui_state()
        tdms_path = app._app_state["path_lookup"].get(label)
        if tdms_path is None:
            return
        app._app_state["tdms_path"] = tdms_path
        self.load_current_file()

    def remove_current_file(self) -> None:
        app = self.app
        if not app._app_state["selected_paths"]:
            return
        current_path = app._app_state["tdms_path"]
        if current_path is None:
            messagebox.showwarning("提示", "没有可移除的文件")
            return
        if not messagebox.askyesno("确认移除", f"确定要移除文件吗？\n\n{current_path.name}"):
            return
        # Clean up current file state
        current_key = str(current_path)
        app._app_state["selected_paths"].remove(current_path)
        app._app_state["current_result_keys"].pop(current_key, None)
        app._app_state["file_ui_cache"].pop(current_key, None)
        # Clean up comparison items from this file
        app._app_state["comparison_items"] = [
            item for item in app._app_state.get("comparison_items", [])
            if item.file_path != current_path
        ]
        app.comparison.refresh_list()
        # Switch to another file or clear
        remaining = app._app_state["selected_paths"]
        if remaining:
            app._app_state["tdms_path"] = remaining[0]
            self.refresh_file_choices(preferred_path=remaining[0])
            self.load_current_file()
        else:
            app._app_state["tdms_path"] = None
            app._app_state["channels"] = None
            app._app_state["segments"] = []
            app._app_state["segment_lookup"] = {}
            app._app_state["segment_colors"] = {}
            app._app_state["prepared"] = None
            app._app_state["fit"] = None
            app._app_state["prepared_by_segment"] = {}
            app._app_state["fit_by_segment"] = {}
            app._app_state["selected_segment_indices"] = []
            app._app_state["active_segment_index"] = 0
            app.channel_info_var.set("")
            self.refresh_file_choices()
            r.draw_placeholder(app)
            app.status_var.set("等待选择数据文件 …")
        log_info(f"移除文件: {current_path}")
        app.status_var.set(f"已移除 {current_path.name}")

    def choose_files(self) -> None:
        app = self.app
        paths = filedialog.askopenfilenames(
            title="选择数据文件",
            filetypes=[
                ("支持的文件", "*.tdms *.txt *.csv *.xlsx *.xls *.cor"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        selected_paths = [Path(path) for path in paths]
        for p_ in selected_paths:
            if p_ not in app._app_state["selected_paths"]:
                app._app_state["selected_paths"].append(p_)
        self.refresh_file_choices(preferred_path=selected_paths[0])
        app._app_state["tdms_path"] = selected_paths[0]
        self.load_current_file()

    def try_formula_or_default(self, text: str, channels: dict, preferred: list[str]) -> str:
        raw = text.strip()
        if raw:
            try:
                normalize_formula(channels, raw, preferred)
                return raw
            except Exception:
                pass
        return f"[{pick_channel_name(channels, preferred)}]"

    def refresh_segments(self, show_error: bool = False) -> bool:
        app = self.app
        channels = app._app_state.get("channels")
        if channels is None:
            return False
        try:
            formula = app.entry_potential_formula.get().strip()
            normalized = normalize_formula(channels, formula, POTENTIAL_PREFERRED_NAMES)
            segments = build_segment_infos(channels, normalized)
            app._app_state["segments"] = segments
            app._app_state["segment_lookup"] = {seg.label: seg.index for seg in segments}
            app._app_state["segment_colors"] = p.merge_active_palette(
                app, app._app_state.get("segment_colors", {}), len(segments)
            )
            selected_text = settings.get_segment_selection_text(app)
            try:
                selected_indices = parse_segment_selection(
                    selected_text, len(segments), app._app_state.get("active_segment_index", 0)
                )
            except Exception:
                selected_indices = [0] if segments else []
            app._app_state["selected_segment_indices"] = selected_indices
            app.segments.refresh_buttons()
            app.status_var.set(f"分段已更新，共 {len(segments)} 段")
            return True
        except Exception as exc:
            if show_error:
                messagebox.showerror("分段更新失败", str(exc))
            else:
                app.status_var.set(f"分段更新失败：{exc}")
            return False

    def load_current_file(self) -> None:
        app = self.app
        tdms_path = app._app_state.get("tdms_path")
        if tdms_path is None:
            return
        app.status_var.set("正在加载数据文件…")
        app.update_idletasks()

        def _task():
            try:
                channels = read_data_all_channels(tdms_path)
                channel_names = list(channels.keys())
                potential_formula = self.try_formula_or_default(
                    app.entry_potential_formula.get(),
                    channels,
                    POTENTIAL_PREFERRED_NAMES,
                )
                current_formula = self.try_formula_or_default(
                    app.entry_current_formula.get(),
                    channels,
                    CURRENT_PREFERRED_NAMES,
                )
                cached_ui = app._app_state["file_ui_cache"].get(str(tdms_path))
                if cached_ui:
                    potential_formula = cached_ui.get("potential_formula") or potential_formula
                    current_formula = cached_ui.get("current_formula") or current_formula
                segments = build_segment_infos(channels, potential_formula)
                segment_labels = [seg.label for seg in segments]

                def _apply_loaded():
                    app._app_state["channels"] = channels
                    app._app_state["segments"] = segments
                    app._app_state["segment_lookup"] = {label: idx for idx, label in enumerate(segment_labels)}
                    app._app_state["segment_colors"] = p.merge_active_palette(
                        app,
                        p.deserialize_segment_colors(app, (cached_ui or {}).get("segment_colors", {})),
                        len(segments),
                    )
                    app._app_state["prepared"] = None
                    app._app_state["fit"] = None
                    app._app_state["prepared_by_segment"] = {}
                    app._app_state["fit_by_segment"] = {}
                    app._app_state["fit_error_by_segment"] = {}
                    app._app_state["selected_segment_indices"] = []
                    app._app_state["active_segment_index"] = 0
                    app._app_state["manual_mode"] = False
                    set_entry_text(app.entry_potential_formula, potential_formula)
                    set_entry_text(app.entry_current_formula, current_formula)
                    if cached_ui:
                        for key, entry_name in [
                            ("e_eq", "e_eq"), ("window_range", "window_range"),
                            ("eta_range", "eta_range"), ("logj_range", "logj_range"),
                            ("min_r2", "min_r2"), ("export_name", "export_name"),
                        ]:
                            entry = getattr(app, f"entry_{entry_name}", None)
                            if entry:
                                set_entry_text(entry, cached_ui.get(key, ""))
                        app.combo_fit_priority.set(cached_ui.get("fit_priority", "斜率更低优先"))
                    else:
                        settings.apply_parameter_settings_to_form(
                            app, app._app_state.get("saved_parameter_defaults", settings.default_parameter_settings())
                        )
                        set_entry_text(app.entry_export_name, tdms_path.stem)
                    preferred_label = cached_ui.get("segment_label") if cached_ui else (
                        segment_labels[0] if segment_labels else None
                    )
                    active_index = app._app_state["segment_lookup"].get(preferred_label, 0) if preferred_label else 0
                    app._app_state["active_segment_index"] = active_index
                    selection_text = cached_ui.get("segment_selection", "1") if cached_ui else "1"
                    try:
                        app._app_state["selected_segment_indices"] = parse_segment_selection(
                            selection_text, len(segments), active_index,
                        )
                    except Exception:
                        app._app_state["selected_segment_indices"] = [active_index] if segments else []
                    app.segments.refresh_buttons()
                    self.refresh_file_choices(preferred_path=tdms_path)
                    app.channel_info_var.set("可用 Channel:\n" + ", ".join(channel_names))
                    app.status_var.set(f"已加载 {tdms_path.name}，共 {len(channel_names)} channel，{len(segments)} 段")
                    log_info(f"加载文件: {tdms_path} ({len(channel_names)} channels, {len(segments)} 段)")
                    r.draw_placeholder(app)
                    app.fitting.restore_or_autorun()

                app.after(0, _apply_loaded)
            except Exception as exc:
                log_error(f"加载文件失败 {tdms_path}: {exc}")
                app.after(0, lambda: app.status_var.set("加载失败"))
                app.after(0, lambda: messagebox.showerror("加载文件失败", str(exc)))

        threading.Thread(target=_task, daemon=True).start()

    def handle_drop(self, event) -> str:
        app = self.app
        try:
            dropped_paths = [Path(item) for item in app.tk.splitlist(event.data)]
            cache_candidates = [path for path in dropped_paths if path.suffix.lower() == ".json"]
            data_candidates = [
                path for path in dropped_paths
                if path.suffix.lower() in {".tdms", ".txt", ".csv", ".xlsx", ".xls", ".cor"}
            ]
            if cache_candidates:
                payload = json.loads(cache_candidates[0].read_text(encoding="utf-8"))
                self.restore_cache_payload(payload)
                app.status_var.set("拖入缓存恢复完成 ✓")
                return "break"
            if data_candidates:
                for p_ in data_candidates:
                    if p_ not in app._app_state["selected_paths"]:
                        app._app_state["selected_paths"].append(p_)
                self.refresh_file_choices(preferred_path=data_candidates[0])
                app._app_state["tdms_path"] = data_candidates[0]
                self.load_current_file()
                app.status_var.set("拖入文件已追加并加载 ✓")
                return "break"
        except Exception as exc:
            messagebox.showerror("拖入文件失败", str(exc))
            app.status_var.set("拖入文件失败")
        return "break"

    def import_cache_dialog(self) -> None:
        app = self.app
        cache_path = filedialog.askopenfilename(
            title="选择缓存文件",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(app._app_state["selected_paths"][0].parent) if app._app_state["selected_paths"] else None,
        )
        if not cache_path:
            return
        try:
            payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
            self.restore_cache_payload(payload)
            app.status_var.set("缓存恢复完成 ✓")
        except Exception as exc:
            messagebox.showerror("缓存恢复失败", str(exc))
            app.status_var.set("缓存恢复失败")

    def restore_cache_payload(self, payload: dict, *, preferred_path: Path | None = None) -> None:
        app = self.app
        selected_paths = [Path(path) for path in payload.get("selected_paths", [])]
        existing_paths = [path for path in selected_paths if path.exists()]
        missing_paths = [path for path in selected_paths if not path.exists()]
        app._app_state["selected_paths"] = existing_paths
        app._app_state["file_ui_cache"] = {
            str(Path(file_key)): value for file_key, value in payload.get("file_ui_cache", {}).items()
        }
        app._app_state["result_cache"] = {
            c.cache_key_from_json(item["key"]): {
                "prepared": prepared_from_dict(item["prepared"]),
                "fit": fit_from_dict(item["fit"]) if item.get("fit") is not None else None,
                "prepared_by_segment": {
                    int(index): prepared_from_dict(value)
                    for index, value in item.get("prepared_by_segment", {}).items()
                },
                "fit_by_segment": {
                    int(index): fit_from_dict(value)
                    for index, value in item.get("fit_by_segment", {}).items()
                },
                "fit_error_by_segment": {
                    int(index): value for index, value in item.get("fit_error_by_segment", {}).items()
                },
                "selected_segment_indices": list(item.get("selected_segment_indices", [])),
                "active_segment_index": int(item.get("active_segment_index", 0)),
                "view_state": item.get("view_state"),
                "limits": item.get("limits"),
            }
            for item in payload.get("result_cache", [])
        }
        app._app_state["current_result_keys"] = {
            str(Path(file_key)): c.cache_key_from_json(cache_key)
            for file_key, cache_key in payload.get("current_result_keys", {}).items()
        }
        app._app_state["comparison_items"] = [
            ComparisonItem(
                item_id=item["item_id"],
                file_path=Path(item["file_path"]),
                file_name=item["file_name"],
                segment_index=item["segment_index"],
                prepared=prepared_from_dict(item["prepared"]),
                fit=fit_from_dict(item["fit"]) if item.get("fit") is not None else None,
                label=item["label"],
                color=item["color"],
                visible=item.get("visible", True),
            )
            for item in payload.get("comparison_items", [])
        ]
        target_path = preferred_path
        if target_path is None:
            raw_current = payload.get("current_path")
            if raw_current:
                target_path = Path(raw_current)
        if target_path not in existing_paths:
            target_path = existing_paths[0] if existing_paths else None
        self.refresh_file_choices(preferred_path=target_path)
        if target_path is not None:
            app._app_state["tdms_path"] = target_path
            self.load_current_file()
        else:
            app._app_state["tdms_path"] = None
            app._app_state["channels"] = None
            app._app_state["segments"] = []
            app._app_state["segment_lookup"] = {}
            app._app_state["segment_colors"] = {}
            app._app_state["selected_segment_indices"] = []
            app._app_state["active_segment_index"] = 0
            app._app_state["prepared_by_segment"] = {}
            app._app_state["fit_by_segment"] = {}
            app._app_state["fit_error_by_segment"] = {}
            app._app_state["prepared"] = None
            app._app_state["fit"] = None
            app.channel_info_var.set("")
            app.status_var.set("缓存已导入，但缓存中的数据文件当前都不可用。")
            r.draw_placeholder(app)

        app.comparison.update_count_badge()
        app.comparison.refresh_list()
        if app._app_state["comparison_mode"]:
            comp.render_comparison(app)
            app.status_var.set("缓存已导入")
        if missing_paths:
            log_warning(f"缓存恢复: {len(missing_paths)} 个文件缺失")
            messagebox.showwarning(
                "部分文件缺失",
                "以下缓存文件未找到，将跳过恢复：\n\n" + "\n".join(str(p_) for p_ in missing_paths[:15]),
            )
