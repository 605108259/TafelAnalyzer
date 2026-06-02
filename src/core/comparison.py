"""对比模式：图表渲染与导出。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import numpy as np
from matplotlib.figure import Figure
from core.render_styles import MAX_DISPLAY_POINTS
from core.rendering import (
    _clear_axes_artists,
    clean_fit_plot_data,
    configure_static_legend,
    compute_tafel_points,
    valid_fit_source_indices,
)

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp

LSV_STYLE_LINE_MARKER = "line_marker"
LSV_STYLE_LINE = "line"
LSV_STYLE_SCATTER = "scatter"
LSV_STYLES = {LSV_STYLE_LINE_MARKER, LSV_STYLE_LINE, LSV_STYLE_SCATTER}
COMPARISON_TOTAL_DISPLAY_POINTS = 5000
COMPARISON_MIN_DISPLAY_POINTS = 100


def _comparison_point_limit(item_count: int) -> int:
    if item_count <= 0:
        return MAX_DISPLAY_POINTS
    return max(
        COMPARISON_MIN_DISPLAY_POINTS,
        min(MAX_DISPLAY_POINTS, COMPARISON_TOTAL_DISPLAY_POINTS // item_count),
    )


def _downsample_display_arrays(
    x: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray | None = None,
    *,
    limit: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    n = int(min(np.asarray(x).size, np.asarray(y).size))
    if n <= int(limit):
        return x[:n], y[:n], None if mask is None else np.asarray(mask)[:n]
    step = max(1, n // int(limit))
    idx = np.arange(0, n, step)
    if mask is None:
        return x[idx], y[idx], None
    return x[idx], y[idx], np.asarray(mask)[idx]


def _compute_tafel_points_for_display(prepared, *, limit: int) -> tuple[np.ndarray, np.ndarray]:
    j, eta, _ = _downsample_display_arrays(prepared.j, prepared.eta, limit=limit)
    n = int(min(j.size, eta.size))
    if n == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    j = np.asarray(j[:n], dtype=float)
    y = np.asarray(eta[:n], dtype=float)
    mask = np.isfinite(j) & np.isfinite(y) & (np.abs(j) > 0.0)
    if not np.any(mask):
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    x = np.log10(np.abs(j[mask]))
    y = y[mask]
    order = np.argsort(x)
    return x[order], y[order]


def comparison_item_id(file_path: Path, segment_index: int) -> str:
    return f"{file_path}::{segment_index}"


def comparison_item_label(item) -> str:
    return getattr(item, "display_label", None) or item.label or f"{item.file_name}-第{item.segment_index + 1}段"


def normalize_lsv_style(style: str | None) -> str:
    text = str(style or "").strip()
    return text if text in LSV_STYLES else LSV_STYLE_LINE_MARKER


def lsv_plot_kwargs(style: str | None, *, linewidth: float, markersize: float) -> dict:
    normalized = normalize_lsv_style(style)
    if normalized == LSV_STYLE_LINE:
        return {"marker": None, "linestyle": "-", "markersize": 0.0, "linewidth": linewidth}
    if normalized == LSV_STYLE_SCATTER:
        return {"marker": "o", "linestyle": "None", "markersize": markersize, "linewidth": 0.0}
    return {"marker": "o", "linestyle": "-", "markersize": markersize, "linewidth": linewidth}


def tafel_window_mask(
    selected_mask: np.ndarray,
    enabled: bool,
    source_indices: np.ndarray | None = None,
) -> np.ndarray:
    selected = np.asarray(selected_mask, dtype=bool).reshape(-1)
    n = int(selected.size)
    if n == 0:
        return selected
    if not enabled or not np.any(selected):
        return np.ones(n, dtype=bool)
    if source_indices is not None:
        source = np.asarray(source_indices, dtype=int).reshape(-1)[:n]
        if source.size == n:
            selected_source = source[selected]
            if selected_source.size:
                pad = int(np.ceil(selected_source.size * 0.2))
                start = int(selected_source.min()) - pad
                end = int(selected_source.max()) + pad
                return (source >= start) & (source <= end)
    selected_positions = np.flatnonzero(selected)
    pad = int(np.ceil(selected_positions.size * 0.2))
    start = max(0, int(selected_positions[0]) - pad)
    end = min(n, int(selected_positions[-1]) + pad + 1)
    mask = np.zeros(n, dtype=bool)
    mask[start:end] = True
    return mask


def _ordered_static_legend(ax, ordered_labels: list[str], *, fontsize: int = 8):
    handles, labels = ax.get_legend_handles_labels()
    pairs = [
        (index, handle, label)
        for index, (handle, label) in enumerate(zip(handles, labels))
        if label and not str(label).startswith("_")
    ]
    if not pairs:
        return None
    label_order = {label: index for index, label in enumerate(ordered_labels)}
    pairs.sort(key=lambda pair: (label_order.get(pair[2], len(label_order)), pair[0]))
    legend = ax.legend(
        [handle for _index, handle, _label in pairs],
        [label for _index, _handle, label in pairs],
        fontsize=fontsize,
        loc="upper right",
    )
    configure_static_legend(legend)
    return legend


def render_comparison_empty(app: TafelAnalyzerApp) -> None:
    from core.theme import MPL_RC, TEXT_SECONDARY

    app.fig.clear()
    with matplotlib.rc_context(MPL_RC):
        ax = app.fig.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "请在单文件分析模式中处理数据\n然后点击 [添加到对比]",
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
    app._app_state["active_chart_mode"] = "comparison"
    app.canvas.draw_idle()


def render_comparison(
    app: TafelAnalyzerApp,
    preserve_view_state: dict | list | None = None,
) -> None:
    from core.theme import MPL_RC, TEXT_PRIMARY
    from core.rendering import (
        apply_plot_view_state,
        capture_plot_view_state,
        current_or_saved_plot_view_state,
    )

    if preserve_view_state is None:
        preserve_view_state = current_or_saved_plot_view_state(app, "comparison")
    visible_items = [item for item in app._app_state["comparison_items"] if item.visible]
    if not visible_items:
        render_comparison_empty(app)
        return
    display_limit = _comparison_point_limit(len(visible_items))

    highlight_row = app._app_state.get("comparison_highlight_row", -1)
    all_items = app._app_state.get("comparison_items", [])
    highlight_id = None
    if 0 <= highlight_row < len(all_items):
        highlight_id = all_items[highlight_row].item_id
    lsv_style = normalize_lsv_style(app._app_state.get("comparison_lsv_style"))
    use_tafel_window = bool(app._app_state.get("comparison_tafel_fit_window", False))
    show_legend = bool(app._app_state.get("comparison_show_legend", True))
    stable_labels = [comparison_item_label(item) for item in visible_items]
    stable_tafel_labels = [
        f"{label} ({item.fit.slope_mv_per_dec:.1f} mV/dec)" if item.fit is not None else label
        for item, label in zip(visible_items, stable_labels)
    ]

    reuse_axes = len(app.fig.axes) >= 2
    if reuse_axes:
        ax0, ax1 = app.fig.axes[:2]
        _clear_axes_artists(ax0)
        _clear_axes_artists(ax1)
    else:
        app.fig.clear()
    with matplotlib.rc_context(MPL_RC):
        if not reuse_axes:
            gs = app.fig.add_gridspec(1, 2, wspace=0.30, left=0.10, right=0.97, top=0.92, bottom=0.12)
            ax0 = app.fig.add_subplot(gs[0])
            ax1 = app.fig.add_subplot(gs[1])

        # Draw non-highlighted items first, then highlighted on top
        draw_order = [it for it in visible_items if it.item_id != highlight_id]
        draw_order += [it for it in visible_items if it.item_id == highlight_id]

        for item in draw_order:
            prepared = item.prepared
            fit = item.fit
            color = item.color
            label = comparison_item_label(item)
            is_highlighted = item.item_id == highlight_id
            lw = 2.5 if is_highlighted else 1.4
            ms = 5.0 if is_highlighted else 3.0
            z = 5 if is_highlighted else 1

            e_show, j_show, _ = _downsample_display_arrays(
                prepared.e, prepared.j, limit=display_limit,
            )
            ax0.plot(
                e_show, j_show,
                **lsv_plot_kwargs(lsv_style, linewidth=lw, markersize=ms),
                color=color, alpha=0.9, label=label, zorder=z,
            )
            if fit is not None:
                fit_indices = valid_fit_source_indices(fit, prepared)
                if fit_indices.size:
                    fit_e, fit_j, _ = _downsample_display_arrays(
                        prepared.e[fit_indices],
                        prepared.j[fit_indices],
                        limit=display_limit,
                    )
                    ax0.scatter(
                        fit_e, fit_j,
                        s=28, color=color, edgecolors="#111827",
                        linewidths=0.5, alpha=0.95, zorder=4,
                        rasterized=True,
                    )

            if fit is not None:
                x_seg, y_seg, mask, source = clean_fit_plot_data(fit)
                if not x_seg.size:
                    continue
                display_mask = tafel_window_mask(mask, use_tafel_window, source)
                x_show = x_seg[display_mask]
                y_show = y_seg[display_mask]
                mask_show = mask[display_mask]
                xs_for_line = x_show[mask_show]
                x_show, y_show, mask_show_ds = _downsample_display_arrays(
                    x_show, y_show, mask_show, limit=display_limit,
                )
                if mask_show_ds is None:
                    mask_show_ds = np.zeros_like(x_show, dtype=bool)
                mask_show = mask_show_ds
                ax1.scatter(
                    x_show[~mask_show], y_show[~mask_show],
                    s=14, alpha=0.2, color=color, zorder=2,
                    rasterized=True,
                )
                ax1.scatter(
                    x_show[mask_show], y_show[mask_show], s=28, color=color,
                    edgecolors="#111827", linewidths=0.5,
                    label=f"{label} ({fit.slope_mv_per_dec:.1f} mV/dec)",
                    zorder=3,
                    rasterized=True,
                )
                xs = xs_for_line
                if xs.size >= 2:
                    margin = max((float(xs.max()) - float(xs.min())) * 0.08, 0.02)
                    x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, 100)
                    y_line = fit.slope_v_per_dec * x_line + fit.intercept_v
                    ax1.plot(x_line, y_line, linewidth=2.0, color=color, linestyle="--", alpha=0.9, zorder=4)
            else:
                x_pts, y_pts = _compute_tafel_points_for_display(
                    prepared, limit=display_limit,
                )
                if x_pts.size:
                    ax1.scatter(
                        x_pts, y_pts, s=14, alpha=0.4, color=color,
                        label=label, zorder=2, rasterized=True,
                    )

        ref = visible_items[0].prepared
        ax0.set_xlabel(ref.e_label, fontsize=11)
        ax0.set_ylabel(ref.j_label, fontsize=11)
        ax0.set_title("电化学数据对比", fontsize=12, color=TEXT_PRIMARY, pad=8)
        ax0.grid(True)
        if show_legend:
            _ordered_static_legend(ax0, stable_labels, fontsize=8)
        ax1.set_xlabel("log10(|j|)", fontsize=11)
        ax1.set_ylabel(ref.tafel_y_label, fontsize=11)
        ax1.set_title("Tafel 斜率对比", fontsize=12, color=TEXT_PRIMARY, pad=8)
        ax1.grid(True)
        if show_legend:
            _ordered_static_legend(ax1, stable_tafel_labels, fontsize=8)

        # Apply user-saved axis label overrides (double-click rename)
        from core.rendering import _apply_override
        overrides = app._app_state.get("axis_label_overrides", {})
        _apply_override(overrides, "comp_ax0_xlabel", ax0.set_xlabel)
        _apply_override(overrides, "comp_ax0_ylabel", ax0.set_ylabel)
        _apply_override(overrides, "comp_ax0_title", ax0.set_title)
        _apply_override(overrides, "comp_ax1_xlabel", ax1.set_xlabel)
        _apply_override(overrides, "comp_ax1_ylabel", ax1.set_ylabel)
        _apply_override(overrides, "comp_ax1_title", ax1.set_title)

        for axis in (ax0, ax1):
            axis.relim(visible_only=True)
            axis.autoscale(enable=True, tight=False)
            axis.autoscale_view()

    app._app_state["compare_plot_default_view_state"] = capture_plot_view_state(app, app.fig)
    apply_plot_view_state(app, [ax0, ax1], preserve_view_state)
    app._app_state["ax_tafel"] = None
    app._app_state["compare_plot_view_state"] = capture_plot_view_state(app, app.fig)
    app._app_state["active_chart_mode"] = "comparison"
    app.canvas.draw_idle()


def build_comparison_export(
    items: list,
    card_bg: str,
    mpl_rc: dict,
    *,
    lsv_style: str = LSV_STYLE_LINE_MARKER,
    tafel_fit_window: bool = False,
) -> tuple[Figure, list[str]]:
    """Build export figure and summary lines for comparison items."""
    export_fig = Figure(figsize=(12, 5.4), dpi=150)
    export_fig.set_facecolor(card_bg)
    with matplotlib.rc_context(mpl_rc):
        gs = export_fig.add_gridspec(1, 2, wspace=0.30, left=0.10, right=0.97, top=0.92, bottom=0.12)
        ax0 = export_fig.add_subplot(gs[0])
        ax1 = export_fig.add_subplot(gs[1])
        for item in items:
            p, f = item.prepared, item.fit
            item_label = comparison_item_label(item)
            ax0.plot(
                p.e, p.j,
                **lsv_plot_kwargs(lsv_style, linewidth=1.4, markersize=3),
                color=item.color, alpha=0.9, label=item_label,
            )
            if f:
                x_seg, y_seg, mask, source = clean_fit_plot_data(f)
                if not x_seg.size:
                    continue
                display_mask = tafel_window_mask(mask, tafel_fit_window, source)
                x_show = x_seg[display_mask]
                y_show = y_seg[display_mask]
                mask_show = mask[display_mask]
                ax1.scatter(x_show[mask_show], y_show[mask_show], s=28, color=item.color, edgecolors="#111827", linewidths=0.5, label=f"{item_label} ({f.slope_mv_per_dec:.1f} mV/dec)", zorder=3)
                xs = x_show[mask_show]
                if xs.size >= 2:
                    margin = max((float(xs.max()) - float(xs.min())) * 0.08, 0.02)
                    x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, 100)
                    ax1.plot(x_line, f.slope_v_per_dec * x_line + f.intercept_v, linewidth=2, color=item.color, linestyle="--", alpha=0.9, zorder=4)
        ref = items[0].prepared
        ax0.set_xlabel(ref.e_label, fontsize=11)
        ax0.set_ylabel(ref.j_label, fontsize=11)
        ax0.set_title("电化学数据对比", fontsize=12, pad=8)
        ax0.grid(True)
        configure_static_legend(ax0.legend(fontsize=8, loc="upper right"))
        ax1.set_xlabel("log10(|j|)", fontsize=11)
        ax1.set_ylabel(ref.tafel_y_label, fontsize=11)
        ax1.set_title("Tafel 斜率对比", fontsize=12, pad=8)
        ax1.grid(True)
        configure_static_legend(ax1.legend(fontsize=8, loc="upper right"))

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
