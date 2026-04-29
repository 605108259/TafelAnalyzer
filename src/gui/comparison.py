"""对比模式：图表渲染与导出。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import numpy as np
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


def comparison_item_id(file_path: Path, segment_index: int) -> str:
    return f"{file_path}::{segment_index}"


def render_comparison_empty(app: TafelAnalyzerApp) -> None:
    from gui.theme import MPL_RC, TEXT_SECONDARY

    app.fig.clear()
    with matplotlib.rc_context(MPL_RC):
        ax = app.fig.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "请在单文件分析模式中处理数据\n然后点击 「📌 添加到对比」",
            ha="center", va="center", fontsize=16,
            color=TEXT_SECONDARY, transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    app._app_state["ax_tafel"] = None
    app._app_state["compare_plot_default_view_state"] = None
    app._app_state["compare_plot_view_state"] = None
    app.canvas.draw_idle()


def render_comparison(
    app: TafelAnalyzerApp,
    preserve_view_state: dict | list | None = None,
) -> None:
    from gui.theme import MPL_RC, TEXT_PRIMARY
    from gui.rendering import (
        apply_plot_view_state,
        capture_plot_view_state,
        enable_draggable_legend,
    )

    if preserve_view_state is None:
        preserve_view_state = (
            capture_plot_view_state(app, app.fig)
            if len(app.fig.axes) >= 2
            else app._app_state.get("compare_plot_view_state")
        )
    visible_items = [item for item in app._app_state["comparison_items"] if item.visible]
    if not visible_items:
        render_comparison_empty(app)
        return

    app.fig.clear()
    with matplotlib.rc_context(MPL_RC):
        gs = app.fig.add_gridspec(1, 2, wspace=0.28, left=0.07, right=0.97, top=0.92, bottom=0.12)
        ax0 = app.fig.add_subplot(gs[0])
        ax1 = app.fig.add_subplot(gs[1])

        for item in visible_items:
            prepared = item.prepared
            fit = item.fit
            color = item.color
            label = item.label

            ax0.plot(
                prepared.e, prepared.j,
                marker="o", linestyle="-", markersize=3.0,
                linewidth=1.4, color=color, alpha=0.9,
                label=label,
            )
            if fit is not None:
                fit_indices = fit.source_indices[fit.selected_mask]
                if fit_indices.size:
                    ax0.scatter(
                        prepared.e[fit_indices], prepared.j[fit_indices],
                        s=28, color=color, edgecolors="#111827",
                        linewidths=0.5, alpha=0.95, zorder=4,
                    )

            if fit is not None:
                x_seg, y_seg, mask = fit.x_log10_j, fit.y_e, fit.selected_mask
                ax1.scatter(x_seg[~mask], y_seg[~mask], s=14, alpha=0.2, color=color, zorder=2)
                ax1.scatter(
                    x_seg[mask], y_seg[mask], s=28, color=color,
                    edgecolors="#111827", linewidths=0.5,
                    label=f"{label} ({fit.slope_mv_per_dec:.1f} mV/dec)",
                    zorder=3,
                )
                xs = x_seg[mask]
                if xs.size >= 2:
                    margin = max((float(xs.max()) - float(xs.min())) * 0.08, 0.02)
                    x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, 100)
                    y_line = fit.slope_v_per_dec * x_line + fit.intercept_v
                    ax1.plot(x_line, y_line, linewidth=2.0, color=color, linestyle="--", alpha=0.9, zorder=4)
            else:
                j_abs = np.abs(prepared.j)
                pos = j_abs > 0
                if np.any(pos):
                    x_pts = np.log10(j_abs[pos])
                    y_pts = prepared.eta[pos]
                    ax1.scatter(x_pts, y_pts, s=14, alpha=0.4, color=color, label=label, zorder=2)

        ref = visible_items[0].prepared
        ax0.set_xlabel(ref.e_label, fontsize=11)
        ax0.set_ylabel(ref.j_label, fontsize=11)
        ax0.set_title("电化学数据对比", fontsize=12, color=TEXT_PRIMARY, pad=8)
        ax0.grid(True)
        legend0 = ax0.legend(fontsize=8, loc="best")
        ax1.set_xlabel("log10(|j|)", fontsize=11)
        ax1.set_ylabel(ref.tafel_y_label, fontsize=11)
        ax1.set_title("Tafel 斜率对比", fontsize=12, color=TEXT_PRIMARY, pad=8)
        ax1.grid(True)
        legend1 = ax1.legend(fontsize=8, loc="best")
        enable_draggable_legend(legend0)
        enable_draggable_legend(legend1)

    app._app_state["compare_plot_default_view_state"] = capture_plot_view_state(app, app.fig)
    apply_plot_view_state(app, [ax0, ax1], preserve_view_state)
    app._app_state["ax_tafel"] = None
    app._app_state["compare_plot_view_state"] = capture_plot_view_state(app, app.fig)
    app.canvas.draw_idle()


def build_comparison_export(
    items: list,
    card_bg: str,
    mpl_rc: dict,
) -> tuple[Figure, list[str]]:
    """Build export figure and summary lines for comparison items."""
    export_fig = Figure(figsize=(12, 5.4), dpi=150)
    export_fig.set_facecolor(card_bg)
    with matplotlib.rc_context(mpl_rc):
        gs = export_fig.add_gridspec(1, 2, wspace=0.28, left=0.07, right=0.97, top=0.92, bottom=0.12)
        ax0 = export_fig.add_subplot(gs[0])
        ax1 = export_fig.add_subplot(gs[1])
        for item in items:
            p, f = item.prepared, item.fit
            ax0.plot(p.e, p.j, marker="o", linestyle="-", markersize=3, linewidth=1.4, color=item.color, alpha=0.9, label=item.label)
            if f:
                x_seg, y_seg, mask = f.x_log10_j, f.y_e, f.selected_mask
                ax1.scatter(x_seg[mask], y_seg[mask], s=28, color=item.color, edgecolors="#111827", linewidths=0.5, label=f"{item.label} ({f.slope_mv_per_dec:.1f} mV/dec)", zorder=3)
                xs = x_seg[mask]
                if xs.size >= 2:
                    margin = max((float(xs.max()) - float(xs.min())) * 0.08, 0.02)
                    x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, 100)
                    ax1.plot(x_line, f.slope_v_per_dec * x_line + f.intercept_v, linewidth=2, color=item.color, linestyle="--", alpha=0.9, zorder=4)
        ref = items[0].prepared
        ax0.set_xlabel(ref.e_label, fontsize=11)
        ax0.set_ylabel(ref.j_label, fontsize=11)
        ax0.set_title("电化学数据对比", fontsize=12, pad=8)
        ax0.grid(True)
        ax0.legend(fontsize=8, loc="best")
        ax1.set_xlabel("log10(|j|)", fontsize=11)
        ax1.set_ylabel(ref.tafel_y_label, fontsize=11)
        ax1.set_title("Tafel 斜率对比", fontsize=12, pad=8)
        ax1.grid(True)
        ax1.legend(fontsize=8, loc="best")

    summary_lines = [
        "跨文件 Tafel 对比汇总",
        f"导出时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"{'标签':<30} {'文件':<30} {'段号':>6} {'E_eq':>8} {'slope(mV/dec)':>15} {'R²':>10} {'拟合点数':>10}",
        "─" * 115,
    ]
    for item in items:
        if item.fit:
            summary_lines.append(
                f"{item.label:<30} {item.file_name:<30} {item.segment_index + 1:>6} "
                f"{item.prepared.e_eq:>8.4f} {item.fit.slope_mv_per_dec:>15.3f} "
                f"{item.fit.r2:>10.6f} {item.fit.selected_count:>6}/{item.fit.x_log10_j.size}"
            )
        else:
            summary_lines.append(f"{item.label:<30} {item.file_name:<30} {item.segment_index + 1:>6} {'—':>8} {'未拟合':>15}")

    return export_fig, summary_lines
