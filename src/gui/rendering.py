"""matplotlib 图表渲染、图例/视图状态管理。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector

from core.types import PreparedSeries, TafelFit

if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp


def clear_toolbar_mode(app: TafelAnalyzerApp) -> None:
    mode_text = str(getattr(app.toolbar, "mode", "")).lower()
    if "zoom" in mode_text:
        app.toolbar.zoom()
    elif "pan" in mode_text:
        app.toolbar.pan()
    app.canvas.get_tk_widget().focus_set()


def reset_origin_view(app: TafelAnalyzerApp) -> None:
    if len(app.fig.axes) < 2:
        app._toolbar_home_original()
        return
    # 直接从图上已绘制的数据重新计算自动缩放极限，
    # 不依赖可能被用户缩放覆盖的缓存状态。
    for ax in app.fig.axes[:2]:
        ax.relim()
        ax.autoscale_view()
    if app._app_state.get("comparison_mode"):
        app._app_state["compare_plot_view_state"] = capture_plot_view_state(app, app.fig)
        app._app_state["compare_plot_default_view_state"] = capture_plot_view_state(app, app.fig)
    else:
        app._app_state["single_plot_view_state"] = capture_plot_view_state(app, app.fig)
        app._app_state["single_plot_default_view_state"] = capture_plot_view_state(app, app.fig)
    app.canvas.draw_idle()


def compute_tafel_points(prepared: PreparedSeries) -> tuple[np.ndarray, np.ndarray]:
    j = np.asarray(prepared.j, dtype=float).reshape(-1)
    y = np.asarray(prepared.eta, dtype=float).reshape(-1)
    n = min(int(j.size), int(y.size))
    j = j[:n]
    y = y[:n]
    mask = np.isfinite(j) & np.isfinite(y) & (np.abs(j) > 0.0)
    if not np.any(mask):
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    x = np.log10(np.abs(j[mask]))
    y = y[mask]
    order = np.argsort(x)
    return x[order], y[order]


MULTI_SEGMENT_TITLE = "多段电化学数据"


def render_figure(
    app: TafelAnalyzerApp,
    target_fig: Figure,
    *,
    display_indices: list[int],
    active_index: int,
    prepared_by_segment: dict[int, PreparedSeries],
    fit_by_segment: dict[int, TafelFit],
    fit_error_by_segment: dict[int, str] | None = None,
):
    from core.types import COMPARISON_COLORS
    from gui.theme import MPL_RC, TEXT_PRIMARY

    target_fig.clear()
    if fit_error_by_segment is None:
        fit_error_by_segment = {}
    ref_prepared = prepared_by_segment.get(active_index) or next(iter(prepared_by_segment.values()))
    with matplotlib.rc_context(MPL_RC):
        gs = target_fig.add_gridspec(1, 2, wspace=0.28, left=0.07, right=0.97, top=0.92, bottom=0.12)
        ax0 = target_fig.add_subplot(gs[0])
        ax1 = target_fig.add_subplot(gs[1])
        for segment_index in display_indices:
            segment_prepared = prepared_by_segment.get(segment_index)
            if segment_prepared is None:
                continue
            color = p_get_segment_color(app, segment_index)
            is_active = segment_index == active_index
            line_width = 1.7 if is_active else 1.0
            alpha = 1.0 if is_active else 0.72
            label = f"第{segment_index + 1}段"
            ax0.plot(
                segment_prepared.e,
                segment_prepared.j,
                marker="o",
                linestyle="-",
                markersize=3.0,
                linewidth=line_width,
                color=color,
                alpha=alpha,
                label=label,
            )
            segment_fit = fit_by_segment.get(segment_index)
            if segment_fit is not None:
                fit_indices = segment_fit.source_indices[segment_fit.selected_mask]
                if fit_indices.size:
                    ax0.scatter(
                        segment_prepared.e[fit_indices],
                        segment_prepared.j[fit_indices],
                        s=30 if is_active else 24,
                        color=color,
                        edgecolors="#111827",
                        linewidths=0.5,
                        alpha=0.95,
                        zorder=4,
                    )
            if segment_fit is None:
                x_seg, y_seg = compute_tafel_points(segment_prepared)
                if x_seg.size:
                    ax1.scatter(
                        x_seg,
                        y_seg,
                        s=18,
                        alpha=0.35 if not is_active else 0.65,
                        color=color,
                        zorder=2,
                    )
            else:
                x_seg = segment_fit.x_log10_j
                y_seg = segment_fit.y_e
                mask = segment_fit.selected_mask
                ax1.scatter(
                    x_seg[~mask],
                    y_seg[~mask],
                    s=18,
                    alpha=0.18 if not is_active else 0.35,
                    color=color,
                    zorder=2,
                )
                ax1.scatter(
                    x_seg[mask],
                    y_seg[mask],
                    s=32 if is_active else 26,
                    color=color,
                    edgecolors="#111827",
                    linewidths=0.5,
                    zorder=3,
                )
                xs = x_seg[mask]
                if xs.size >= 2:
                    margin = max((float(xs.max()) - float(xs.min())) * 0.08, 0.02)
                    x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, 100)
                    y_line = segment_fit.slope_v_per_dec * x_line + segment_fit.intercept_v
                    slope_label = f"第{segment_index + 1}段, {segment_fit.slope_mv_per_dec:.1f} mV/dec"
                    ax1.plot(
                        x_line,
                        y_line,
                        linewidth=2.1 if is_active else 1.4,
                        color=color,
                        linestyle="--",
                        alpha=0.95 if is_active else 0.8,
                        label=slope_label,
                        zorder=4,
                    )
        active_fit = fit_by_segment.get(active_index)
        active_error = fit_error_by_segment.get(active_index)
        ax0.set_xlabel(ref_prepared.e_label, fontsize=11)
        ax0.set_ylabel(ref_prepared.j_label, fontsize=11)
        ax0.set_title(
            MULTI_SEGMENT_TITLE if len(display_indices) > 1 else f"第{ref_prepared.segment.index + 1}段电化学数据",
            fontsize=12,
            color=TEXT_PRIMARY,
            pad=8,
        )
        ax0.grid(True)
        legend0 = ax0.legend(fontsize=8, loc="best")
        if active_fit is None:
            title = f"Tafel 拟合失败 — 第{active_index + 1}段"
            if active_error:
                title = f"{title} | {active_error.strip()[:60]}"
            ax1.set_title(title, fontsize=12, color=TEXT_PRIMARY, pad=8)
        else:
            ax1.set_title(
                f"当前分段第{active_index + 1}段 — {active_fit.slope_mv_per_dec:.2f} mV/dec, R²={active_fit.r2:.4f}",
                fontsize=12,
                color=TEXT_PRIMARY,
                pad=8,
            )
        ax1.set_xlabel("log10(|j|)", fontsize=11)
        ax1.set_ylabel(ref_prepared.tafel_y_label, fontsize=11)
        ax1.grid(True)
        legend1 = ax1.legend(fontsize=8, loc="best")
        enable_draggable_legend(legend0)
        enable_draggable_legend(legend1)
    return ax0, ax1


def enable_draggable_legend(legend) -> None:
    if legend is None:
        return
    try:
        legend.set_draggable(True, use_blit=False, update="bbox")
    except TypeError:
        try:
            legend.set_draggable(True)
        except Exception:
            pass
    except Exception:
        pass


def capture_legend_state(axis) -> dict | None:
    legend = axis.get_legend()
    if legend is None:
        return None
    state_data: dict[str, object] = {"loc": getattr(legend, "_loc", None)}
    try:
        bbox_anchor = legend.get_bbox_to_anchor()
        if bbox_anchor is not None:
            bbox_axes = bbox_anchor.transformed(axis.transAxes.inverted())
            bounds = [float(v) for v in bbox_axes.bounds]
            if len(bounds) == 4 and all(np.isfinite(bounds)):
                state_data["bbox"] = bounds
    except Exception:
        pass
    return state_data


def apply_legend_state(app: TafelAnalyzerApp, axis, legend_state: dict | None) -> None:
    legend = axis.get_legend()
    if legend is None:
        return
    if legend_state:
        try:
            loc = legend_state.get("loc")
            if loc is not None:
                if hasattr(legend, "set_loc"):
                    legend.set_loc(loc)
                else:
                    legend._loc = loc
            bbox = legend_state.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(np.isfinite(bbox)):
                legend.set_bbox_to_anchor(tuple(float(v) for v in bbox), transform=axis.transAxes)
        except Exception:
            pass
    enable_draggable_legend(legend)


def capture_plot_view_state(app: TafelAnalyzerApp, target_fig: Figure | None = None) -> dict | None:
    active_fig = target_fig or app.fig
    axes = active_fig.axes[:2]
    if len(axes) < 2:
        return None
    return {
        "axes": [
            {
                "xlim": [float(v) for v in axis.get_xlim()],
                "ylim": [float(v) for v in axis.get_ylim()],
                "legend": capture_legend_state(axis),
            }
            for axis in axes
        ]
    }


def view_state_from_legacy_limits(
    limits: list[tuple[tuple[float, float], tuple[float, float]]] | None,
) -> dict | None:
    if not limits:
        return None
    axes: list[dict[str, object]] = []
    for limit in limits[:2]:
        if not isinstance(limit, (list, tuple)) or len(limit) != 2:
            return None
        xlim, ylim = limit
        axes.append(
            {
                "xlim": [float(v) for v in xlim],
                "ylim": [float(v) for v in ylim],
                "legend": None,
            }
        )
    return {"axes": axes} if axes else None


def apply_plot_view_state(
    app: TafelAnalyzerApp,
    axes: list,
    view_state: dict | list | None,
) -> None:
    if isinstance(view_state, list):
        view_state = view_state_from_legacy_limits(view_state)
    if not isinstance(view_state, dict):
        return
    for axis, axis_state in zip(axes[:2], view_state.get("axes", [])):
        try:
            xlim = axis_state.get("xlim")
            ylim = axis_state.get("ylim")
            if isinstance(xlim, (list, tuple)) and len(xlim) == 2:
                axis.set_xlim(float(xlim[0]), float(xlim[1]))
            if isinstance(ylim, (list, tuple)) and len(ylim) == 2:
                axis.set_ylim(float(ylim[0]), float(ylim[1]))
        except Exception:
            pass
        apply_legend_state(app, axis, axis_state.get("legend"))


def capture_axes_limits(app: TafelAnalyzerApp) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    limits: list[tuple[tuple[float, float], tuple[float, float]]] = []
    view_state = capture_plot_view_state(app, app.fig)
    if not view_state:
        return limits
    for axis_state in view_state.get("axes", []):
        xlim = tuple(float(v) for v in axis_state.get("xlim", ()))
        ylim = tuple(float(v) for v in axis_state.get("ylim", ()))
        if len(xlim) == 2 and len(ylim) == 2:
            limits.append((xlim, ylim))
    return limits


def refresh_selector(app: TafelAnalyzerApp) -> None:
    selector = app._app_state.get("selector")
    if selector is not None:
        try:
            selector.set_active(False)
            selector.disconnect_events()
        except Exception:
            pass
    ax_tafel = app._app_state.get("ax_tafel")
    if ax_tafel is None:
        app._app_state["selector"] = None
        return
    selector = RectangleSelector(
        ax_tafel,
        app.fitting.on_manual_select,
        useblit=True,
        button=[1],
        minspanx=0.01,
        minspany=0.01,
        spancoords="data",
        interactive=False,
        props={"facecolor": "#60a5fa", "edgecolor": "#2563eb", "alpha": 0.18, "fill": True},
    )
    selector.set_active(bool(app._app_state.get("manual_mode", False)))
    app._app_state["selector"] = selector


def draw(
    app: TafelAnalyzerApp,
    prepared: PreparedSeries,
    fit: TafelFit | None,
    preserve_view_state: dict | list | None = None,
    *,
    fit_error: str | None = None,
) -> None:
    if preserve_view_state is None:
        preserve_view_state = (
            capture_plot_view_state(app, app.fig)
            if len(app.fig.axes) >= 2
            else app._app_state.get("single_plot_view_state")
        )
    active_index = int(app._app_state.get("active_segment_index", prepared.segment.index))
    selected_indices = list(app._app_state.get("selected_segment_indices", []))
    display_indices = sorted(set(selected_indices))
    p_map = app._app_state.get("prepared_by_segment") or {prepared.segment.index: prepared}
    f_map = app._app_state.get("fit_by_segment") or ({prepared.segment.index: fit} if fit is not None else {})
    fe_map = dict(app._app_state.get("fit_error_by_segment") or {})
    if fit_error and active_index not in fe_map:
        fe_map[active_index] = fit_error
    ax_left, ax_tafel = render_figure(
        app,
        app.fig,
        display_indices=display_indices,
        active_index=active_index,
        prepared_by_segment=p_map,
        fit_by_segment=f_map,
        fit_error_by_segment=fe_map,
    )
    app._app_state["single_plot_default_view_state"] = capture_plot_view_state(app, app.fig)
    apply_plot_view_state(app, [ax_left, ax_tafel], preserve_view_state)
    app._app_state["ax_tafel"] = ax_tafel
    app._app_state["single_plot_view_state"] = capture_plot_view_state(app, app.fig)
    app.canvas.draw_idle()
    refresh_selector(app)


def draw_placeholder(app: TafelAnalyzerApp) -> None:
    from gui.theme import MPL_RC, TEXT_SECONDARY

    app.fig.clear()
    with matplotlib.rc_context(MPL_RC):
        ax = app.fig.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "请选择数据文件并输入公式\n手动模式下可在右侧 Tafel 图框选区域",
            ha="center",
            va="center",
            fontsize=16,
            color=TEXT_SECONDARY,
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    app._app_state["ax_tafel"] = None
    app._app_state["single_plot_default_view_state"] = None
    app._app_state["single_plot_view_state"] = None
    app.canvas.draw_idle()
    refresh_selector(app)


# Avoid circular import - palette functions needed by render_figure
def p_get_segment_color(app, segment_index, file_path=None):
    from gui.palette import get_segment_color
    return get_segment_color(app, segment_index, file_path=file_path)


def draw_placeholder_fig(fig, canvas, axes_list):
    """Draw placeholder on matplotlib figure/canvas (Qt-compatible)."""
    fig.clear()
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, "请选择数据文件并输入公式\n手动模式下可在右侧 Tafel 图框选区域",
            ha="center", va="center", fontsize=16, color="#475569",
            transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    canvas.draw_idle()
