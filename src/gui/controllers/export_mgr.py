from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from tkinter import filedialog, messagebox

from matplotlib.figure import Figure

from core.export import export_processed_txt, export_fit_npz
from gui.widgets import resolved_output_stem
from gui.theme import CARD_BG, MPL_RC
from gui import rendering as r
from gui import cache as c
from gui import comparison as comp
from gui.logger import log_info, log_error

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


class ExportManager:
    def __init__(self, app: TafelAnalyzerApp):
        self.app = app

    def export_segment_result(
        self,
        out_dir_path: Path,
        tdms_path: Path,
        export_name: str,
        prepared,
        fit,
        *,
        force_segment_suffix: bool,
    ) -> tuple[Path, Path, Path]:
        app = self.app
        stem = resolved_output_stem(tdms_path, export_name)
        if force_segment_suffix:
            stem = f"{stem}_seg{prepared.segment.index + 1}"
        txt_path = export_processed_txt(out_dir_path / f"{stem}.txt", prepared, fit)
        npz_path = export_fit_npz(out_dir_path / f"{stem}_tafel_fit.npz", prepared, fit)
        segment_fig = Figure(figsize=(10.8, 6.6), dpi=120)
        segment_fig.set_facecolor(CARD_BG)
        r.render_figure(
            app, segment_fig,
            display_indices=[prepared.segment.index],
            active_index=prepared.segment.index,
            prepared_by_segment={prepared.segment.index: prepared},
            fit_by_segment={prepared.segment.index: fit},
        )
        fig_path = out_dir_path / f"{stem}_tafel.png"
        segment_fig.savefig(fig_path, dpi=180, bbox_inches="tight")
        return txt_path, fig_path, npz_path

    def export_current(self) -> None:
        app = self.app
        if app._app_state["prepared"] is None or app._app_state["tdms_path"] is None:
            messagebox.showwarning("提示", "请先完成一次拟合")
            return
        if not app._app_state.get("selected_segment_indices"):
            messagebox.showwarning("提示", "请先在分段面板中勾选要导出的分段")
            return
        out_dir = filedialog.askdirectory(
            title="选择导出目录", initialdir=str(app._app_state["tdms_path"].parent)
        )
        if not out_dir:
            return
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
        try:
            success: list[str] = []
            failed: list[str] = []
            for segment_index in app._app_state.get("selected_segment_indices", []):
                prepared = app._app_state["prepared_by_segment"].get(segment_index)
                fit = app._app_state["fit_by_segment"].get(segment_index)
                if prepared is None or fit is None:
                    failed.append(f"第{segment_index + 1}段")
                    continue
                txt_path, fig_path, npz_path = self.export_segment_result(
                    out_dir_path, app._app_state["tdms_path"],
                    app.entry_export_name.get(), prepared, fit,
                    force_segment_suffix=len(app._app_state.get("selected_segment_indices", [])) > 1,
                )
                success.append(f"第{segment_index + 1}段 -> {txt_path.name} | {fig_path.name} | {npz_path.name}")
            app.status_var.set("导出完成 ✓")
            log_info(f"导出 {len(success)} 段 -> {out_dir_path}")
            summary = "导出完成！\n\n" + "\n".join(success[:12])
            if failed:
                summary += "\n\n未导出分段:\n" + "\n".join(failed[:12])
            summary += f"\n\n目录: {out_dir_path}"
            messagebox.showinfo("导出成功", summary)
        except Exception as exc:
            log_error(f"导出失败: {exc}")
            app.status_var.set("导出失败")
            messagebox.showerror("导出失败", str(exc))

    def run_batch(self) -> None:
        app = self.app
        if not app._app_state["selected_paths"]:
            messagebox.showwarning("提示", "请先选择数据文件")
            return
        processed_paths = [
            path for path in app._app_state["selected_paths"]
            if str(path) in app._app_state["current_result_keys"]
        ]
        if not processed_paths:
            messagebox.showwarning("提示", "当前没有已处理文件可导出")
            return
        out_dir = filedialog.askdirectory(
            title="选择批量导出目录",
            initialdir=str(app._app_state["selected_paths"][0].parent),
        )
        if not out_dir:
            return
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
        app.btn_batch.configure(state="disabled")
        app.status_var.set("正在批量导出已处理文件…")
        app.update_idletasks()

        def _task():
            success: list[str] = []
            failed: list[str] = []
            batch_fig = Figure(figsize=(10.8, 6.6), dpi=120)
            batch_fig.set_facecolor(CARD_BG)
            try:
                used_stems: set[str] = set()
                for tdms_path in processed_paths:
                    try:
                        cache_key = app._app_state["current_result_keys"][str(tdms_path)]
                        cached = app._app_state["result_cache"].get(cache_key)
                        if cached is None:
                            raise ValueError("找不到对应的缓存结果")
                        ui_state = app._app_state["file_ui_cache"].get(str(tdms_path), {})
                        stem = resolved_output_stem(tdms_path, ui_state.get("export_name", ""))
                        exported_segments = 0
                        for segment_index in cached.get("selected_segment_indices", []):
                            prepared = cached.get("prepared_by_segment", {}).get(segment_index)
                            fit = cached.get("fit_by_segment", {}).get(segment_index)
                            if prepared is None or fit is None:
                                continue
                            segment_stem = stem if len(cached.get("selected_segment_indices", [])) <= 1 else f"{stem}_seg{segment_index + 1}"
                            base_stem = segment_stem
                            suffix = 2
                            while segment_stem in used_stems:
                                segment_stem = f"{base_stem}_{suffix}"
                                suffix += 1
                            used_stems.add(segment_stem)
                            export_processed_txt(out_dir_path / f"{segment_stem}.txt", prepared, fit)
                            export_fit_npz(out_dir_path / f"{segment_stem}_tafel_fit.npz", prepared, fit)
                            r.render_figure(
                                app, batch_fig,
                                display_indices=[segment_index],
                                active_index=segment_index,
                                prepared_by_segment={segment_index: prepared},
                                fit_by_segment={segment_index: fit},
                            )
                            batch_fig.savefig(out_dir_path / f"{segment_stem}_tafel.png", dpi=180, bbox_inches="tight")
                            exported_segments += 1
                        success.append(f"{tdms_path.name} -> {exported_segments} 段")
                    except Exception as exc:
                        failed.append(f"{tdms_path.name}: {exc}")
                cache_path = c.export_cache_file(app, out_dir_path / "tdms_tafel_cache.json")

                def _finish():
                    app.status_var.set("批量导出完成 ✓")
                    log_info(f"批量导出: 成功 {len(success)}, 失败 {len(failed)} -> {out_dir_path}")
                    lines = [f"成功 {len(success)} 个", f"失败 {len(failed)} 个", "", *success]
                    if failed:
                        lines.extend(["", "失败列表:", *failed])
                    lines.extend(["", f"缓存文件: {cache_path.name}"])
                    app.status_var.set("\n".join(lines))
                    summary = (
                        f"成功导出 {len(success)} 个，失败 {len(failed)} 个。"
                        f"\n输出目录: {out_dir_path}\n缓存文件: {cache_path.name}"
                    )
                    if failed:
                        summary += "\n\n失败详情:\n" + "\n".join(failed[:10])
                    messagebox.showinfo("批量导出完成", summary)

                app.after(0, _finish)
            except Exception as exc:
                app.after(0, lambda: app.status_var.set("批量导出失败"))
                app.after(0, lambda: messagebox.showerror("批量导出失败", str(exc)))
            finally:
                app.after(0, lambda: app.btn_batch.configure(state="normal"))

        threading.Thread(target=_task, daemon=True).start()

    def export_comparison(self) -> None:
        app = self.app
        items = [item for item in app._app_state["comparison_items"] if item.visible]
        if not items:
            messagebox.showwarning("提示", "没有可见的对比项")
            return
        out_dir = filedialog.askdirectory(title="选择对比图导出目录")
        if not out_dir:
            return
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
        try:
            export_fig, summary_lines = comp.build_comparison_export(items, CARD_BG, MPL_RC)
            fig_path = out_dir_path / "comparison_tafel.png"
            export_fig.savefig(fig_path, dpi=200, bbox_inches="tight")
            summary_path = out_dir_path / "comparison_summary.txt"
            summary_path.write_text("\n".join(summary_lines), encoding="utf-8-sig")
            app.status_var.set("对比图导出完成 ✓")
            log_info(f"对比图导出: {len(items)} 项 -> {out_dir_path}")
            messagebox.showinfo("导出成功", f"已导出：\n• {fig_path.name}\n• {summary_path.name}\n\n目录: {out_dir_path}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
