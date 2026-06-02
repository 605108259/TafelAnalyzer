"""matplotlib 图表渲染、图例/视图状态管理。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import matplotlib
import numpy as np
from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector

from core.data_cleaning import valid_measurement_mask
from core.types import PreparedSeries, TafelFit
from core.render_styles import (
    MAX_DISPLAY_POINTS,
    LINEWIDTH_ACTIVE, LINEWIDTH_INACTIVE, LINEWIDTH_DEFAULT,
    LINEWIDTH_FIT_ACTIVE, LINEWIDTH_FIT_INACTIVE, LINEWIDTH_FIT_DEFAULT,
    ALPHA_ACTIVE, ALPHA_INACTIVE, ALPHA_DEFAULT,
    ALPHA_SCATTER_SELECTED,
    ALPHA_SCATTER_DESELECTED_ACTIVE, ALPHA_SCATTER_DESELECTED_INACTIVE, ALPHA_SCATTER_DESELECTED_DEFAULT,
    ALPHA_SCATTER_NO_FIT_ACTIVE, ALPHA_SCATTER_NO_FIT_INACTIVE, ALPHA_SCATTER_NO_FIT_DEFAULT,
    ALPHA_FIT_LINE_ACTIVE, ALPHA_FIT_LINE_INACTIVE, ALPHA_FIT_LINE_DEFAULT,
    MARKERSIZE_ACTIVE, MARKERSIZE_INACTIVE, MARKERSIZE_DEFAULT,
    SCATTER_RAW_FIT_ACTIVE, SCATTER_RAW_FIT_DEFAULT,
    SCATTER_FIT_SELECTED_ACTIVE, SCATTER_FIT_SELECTED_DEFAULT, SCATTER_FIT_SELECTED_INACTIVE,
    SCATTER_FIT_DESELECTED_ACTIVE, SCATTER_FIT_DESELECTED_DEFAULT, SCATTER_FIT_DESELECTED_INACTIVE,
    SCATTER_NO_FIT_ACTIVE, SCATTER_NO_FIT_DEFAULT, SCATTER_NO_FIT_INACTIVE,
    EDGEWIDTH_ACTIVE, EDGEWIDTH_INACTIVE,
    GRIDSPEC_WSPACE, GRIDSPEC_LEFT, GRIDSPEC_RIGHT, GRIDSPEC_TOP, GRIDSPEC_BOTTOM,
    FIT_LINE_MARGIN_FRAC, FIT_LINE_MARGIN_MIN, FIT_LINE_POINTS,
    FONTSIZE_TITLE, FONTSIZE_LABEL, FONTSIZE_LEGEND, FONTSIZE_PLACEHOLDER,
)

_log = logging.getLogger(__name__)


def _safe_set_legend_loc(legend, loc) -> bool:
    try:
        if hasattr(legend, "set_loc"):
            legend.set_loc(loc)
            return True
        try:
            legend._loc = loc
        except Exception:
            _log.debug("Failed to set legend._loc to %s", loc, exc_info=True)
            return False
        return True
    except Exception:
        _log.debug("Failed to set legend location to %s", loc, exc_info=True)
        return False

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


def persist_current_plot_view_state(app: TafelAnalyzerApp) -> None:
    mode = app._app_state.get("active_chart_mode")
    if mode not in {"single", "comparison"} or len(app.fig.axes) < 2:
        return
    key = "single_plot_view_state" if mode == "single" else "compare_plot_view_state"
    app._app_state[key] = capture_plot_view_state(app, app.fig)


def current_or_saved_plot_view_state(
    app: TafelAnalyzerApp,
    mode: str,
) -> dict | list | None:
    key = "single_plot_view_state" if mode == "single" else "compare_plot_view_state"
    if app._app_state.get("active_chart_mode") == mode and len(app.fig.axes) >= 2:
        return capture_plot_view_state(app, app.fig)
    return app._app_state.get(key)


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


def clean_fit_plot_data(fit: TafelFit) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(fit.x_log10_j, dtype=float).reshape(-1)
    y = np.asarray(fit.y_e, dtype=float).reshape(-1)
    selected = np.asarray(fit.selected_mask, dtype=bool).reshape(-1)
    source = np.asarray(fit.source_indices, dtype=int).reshape(-1)
    n = min(x.size, y.size, selected.size, source.size)
    x = x[:n]
    y = y[:n]
    selected = selected[:n]
    source = source[:n]
    valid = valid_measurement_mask(x, y)
    return x[valid], y[valid], selected[valid], source[valid]


def clean_fit_plot_arrays(fit: TafelFit) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, selected, _source = clean_fit_plot_data(fit)
    return x, y, selected


def valid_fit_source_indices(fit: TafelFit, prepared: PreparedSeries) -> np.ndarray:
    selected = np.asarray(fit.selected_mask, dtype=bool).reshape(-1)
    source = np.asarray(fit.source_indices, dtype=int).reshape(-1)
    n = min(selected.size, source.size)
    indices = source[:n][selected[:n]]
    return indices[(indices >= 0) & (indices < int(prepared.e.size))]


MULTI_SEGMENT_TITLE = "多段电化学数据"


def _compute_segment_styles(
    has_active: bool,
    is_active: bool,
) -> dict:
    """Compute visual style constants for a segment based on active state."""
    return {
        "color": None,  # filled per-segment by caller
        "is_active": is_active,
        "z": 6 if is_active else 1,
        "linewidth": LINEWIDTH_ACTIVE if is_active else (LINEWIDTH_DEFAULT if not has_active else LINEWIDTH_INACTIVE),
        "alpha": ALPHA_ACTIVE if is_active else (ALPHA_DEFAULT if not has_active else ALPHA_INACTIVE),
        "markersize": MARKERSIZE_ACTIVE if is_active else (MARKERSIZE_DEFAULT if not has_active else MARKERSIZE_INACTIVE),
        "edgewidth": EDGEWIDTH_ACTIVE if is_active else EDGEWIDTH_INACTIVE,
    }


def _apply_override(overrides: dict, key: str, setter) -> None:
    """If *key* exists in *overrides*, call *setter* with its value."""
    if key in overrides:
        setter(overrides[key])


def _downsample_for_display(x: np.ndarray, y: np.ndarray, mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Reduce point count to MAX_DISPLAY_POINTS via systematic sampling.

    Returns (x_ds, y_ds, mask_ds).  If *mask* is None it is returned as-is.
    Visually lossless at typical chart widths, but 10-50× faster Agg rendering.
    """
    n = int(x.size)
    if n <= MAX_DISPLAY_POINTS:
        return x, y, mask
    step = max(1, n // MAX_DISPLAY_POINTS)
    idx = np.arange(0, n, step)
    if mask is not None:
        return x[idx], y[idx], np.asarray(mask[idx], dtype=bool)
    return x[idx], y[idx], None


def _render_ej_plot(
    ax,
    display_indices: list[int],
    prepared_by_segment: dict,
    fit_by_segment: dict,
    segment_styles: dict[int, dict],
) -> None:
    """Render the E-j scatter/line plot on *ax*."""
    for segment_index in display_indices:
        segment_prepared = prepared_by_segment.get(segment_index)
        if segment_prepared is None:
            continue
        style = segment_styles[segment_index]
        color = style["color"]
        is_active = style["is_active"]
        z = style["z"]
        label = f"第{segment_index + 1}段"
        _pe, _pj, _ = _downsample_for_display(
            segment_prepared.e, segment_prepared.j)
        ax.plot(
            _pe, _pj,
            marker="o",
            linestyle="-",
            markersize=style["markersize"],
            linewidth=style["linewidth"],
            color=color,
            alpha=style["alpha"],
            label=label,
            zorder=z,
        )
        segment_fit = fit_by_segment.get(segment_index)
        if segment_fit is not None:
            fit_indices = valid_fit_source_indices(segment_fit, segment_prepared)
            if fit_indices.size:
                _ex, _ej, _ = _downsample_for_display(
                    segment_prepared.e[fit_indices], segment_prepared.j[fit_indices])
                ax.scatter(
                    _ex, _ej,
                    s=SCATTER_RAW_FIT_ACTIVE if is_active else SCATTER_RAW_FIT_DEFAULT,
                    color=color,
                    edgecolors="#111827",
                    linewidths=style["edgewidth"],
                    alpha=ALPHA_SCATTER_SELECTED,
                    zorder=z + 1,
                    rasterized=True,
                )


def _render_tafel_plot(
    ax,
    display_indices: list[int],
    prepared_by_segment: dict,
    fit_by_segment: dict,
    segment_styles: dict[int, dict],
    manual_fit_regions: dict[int, dict] | None = None,
) -> None:
    """Render the Tafel plot (log |j| vs E) on *ax*."""
    if manual_fit_regions is None:
        manual_fit_regions = {}
    for segment_index in display_indices:
        segment_prepared = prepared_by_segment.get(segment_index)
        if segment_prepared is None:
            continue
        style = segment_styles[segment_index]
        color = style["color"]
        is_active = style["is_active"]
        has_active = style.get("has_active", True)
        z = style["z"]
        segment_fit = fit_by_segment.get(segment_index)
        if segment_fit is None:
            x_seg, y_seg = compute_tafel_points(segment_prepared)
            if x_seg.size:
                _tx, _ty, _ = _downsample_for_display(x_seg, y_seg)
                ax.scatter(
                    _tx, _ty,
                    s=SCATTER_NO_FIT_ACTIVE if is_active else (SCATTER_NO_FIT_DEFAULT if not has_active else SCATTER_NO_FIT_INACTIVE),
                    alpha=ALPHA_SCATTER_NO_FIT_ACTIVE if is_active else (ALPHA_SCATTER_NO_FIT_DEFAULT if not has_active else ALPHA_SCATTER_NO_FIT_INACTIVE),
                    color=color,
                    zorder=z,
                    rasterized=True,
                )
        else:
            x_seg, y_seg, mask = clean_fit_plot_arrays(segment_fit)
            if not x_seg.size:
                continue

            # Downsample for display (fitting uses full data)
            x_ds, y_ds, mask_ds = _downsample_for_display(x_seg, y_seg, mask)
            if mask_ds is None:
                mask_ds = np.zeros_like(x_ds, dtype=bool)
            ax.scatter(
                x_ds[~mask_ds], y_ds[~mask_ds],
                s=SCATTER_FIT_DESELECTED_ACTIVE if is_active else (SCATTER_FIT_DESELECTED_DEFAULT if not has_active else SCATTER_FIT_DESELECTED_INACTIVE),
                alpha=ALPHA_SCATTER_DESELECTED_ACTIVE if is_active else (ALPHA_SCATTER_DESELECTED_DEFAULT if not has_active else ALPHA_SCATTER_DESELECTED_INACTIVE),
                color=color,
                zorder=z,
                rasterized=True,
            )
            ax.scatter(
                x_ds[mask_ds], y_ds[mask_ds],
                s=SCATTER_FIT_SELECTED_ACTIVE if is_active else (SCATTER_FIT_SELECTED_DEFAULT if not has_active else SCATTER_FIT_SELECTED_INACTIVE),
                color=color,
                edgecolors="#111827",
                linewidths=style["edgewidth"],
                zorder=z + 1,
                rasterized=True,
            )
            xs = x_seg[mask]
            if xs.size >= 2:
                margin = max((float(xs.max()) - float(xs.min())) * FIT_LINE_MARGIN_FRAC, FIT_LINE_MARGIN_MIN)
                x_line = np.linspace(float(xs.min()) - margin, float(xs.max()) + margin, FIT_LINE_POINTS)
                y_line = segment_fit.slope_v_per_dec * x_line + segment_fit.intercept_v
                slope_label = f"第{segment_index + 1}段, {segment_fit.slope_mv_per_dec:.1f} mV/dec"
                ax.plot(
                    x_line,
                    y_line,
                    linewidth=LINEWIDTH_FIT_ACTIVE if is_active else (LINEWIDTH_FIT_DEFAULT if not has_active else LINEWIDTH_FIT_INACTIVE),
                    color=color,
                    linestyle="--",
                    alpha=ALPHA_FIT_LINE_ACTIVE if is_active else (ALPHA_FIT_LINE_DEFAULT if not has_active else ALPHA_FIT_LINE_INACTIVE),
                    label=slope_label,
                    zorder=z + 2,
                )
            region = manual_fit_regions.get(segment_index) or manual_fit_regions.get(str(segment_index))
            if segment_fit.mode == "manual" and isinstance(region, dict):
                try:
                    x_min = float(region["x_min"])
                    x_max = float(region["x_max"])
                    y_min = float(region["y_min"])
                    y_max = float(region["y_max"])
                except (KeyError, TypeError, ValueError):
                    continue
                ax.add_patch(Rectangle(
                    (min(x_min, x_max), min(y_min, y_max)),
                    abs(x_max - x_min),
                    abs(y_max - y_min),
                    fill=False,
                    edgecolor=color,
                    linewidth=1.4,
                    linestyle=":",
                    alpha=0.9,
                    zorder=z + 3,
                ))


def _clear_axes_artists(ax) -> None:
    """Remove all plotted artists from an axis without destroying the axis itself.

    Much cheaper than fig.clear() — preserves gridspec, subplot positions,
    tick state, and axis limits.
    """
    for line in list(ax.lines):
        line.remove()
    for coll in list(ax.collections):
        coll.remove()
    for patch in list(ax.patches):
        patch.remove()
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()


def _needs_full_rebuild(app: TafelAnalyzerApp, target_fig: Figure) -> bool:
    """Return True if the figure cache is stale and needs a full rebuild."""
    cache = app._app_state.get("_chart_cache")
    if cache is None:
        return True
    if cache.get("fig_id") != id(target_fig):
        return True
    if len(target_fig.axes) < 2:
        return True
    return False


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
    from core.theme import MPL_RC, TEXT_PRIMARY

    if fit_error_by_segment is None:
        fit_error_by_segment = {}

    # ━━ Empty data path ━━
    if not prepared_by_segment:
        target_fig.clear()
        app._app_state["_chart_cache"] = None
        with matplotlib.rc_context(MPL_RC):
            gs = target_fig.add_gridspec(1, 2, wspace=GRIDSPEC_WSPACE, left=GRIDSPEC_LEFT, right=GRIDSPEC_RIGHT, top=GRIDSPEC_TOP, bottom=GRIDSPEC_BOTTOM)
            ax0 = target_fig.add_subplot(gs[0])
            ax1 = target_fig.add_subplot(gs[1])
            ax0.grid(True)
            ax1.grid(True)
            ax0.set_title("无数据", fontsize=FONTSIZE_TITLE, color=TEXT_PRIMARY, pad=8)
            ax1.set_title("Tafel", fontsize=FONTSIZE_TITLE, color=TEXT_PRIMARY, pad=8)
        return ax0, ax1

    ref_prepared = prepared_by_segment.get(active_index) or next(iter(prepared_by_segment.values()))
    has_active = active_index in prepared_by_segment

    # ━━ Decide: full rebuild or incremental ━━
    full_rebuild = _needs_full_rebuild(app, target_fig)

    if full_rebuild:
        target_fig.clear()
        # Cache figure identity for next incremental check
        app._app_state["_chart_cache"] = {"fig_id": id(target_fig)}
    else:
        # Incremental: reuse existing axes, only strip artists
        ax0, ax1 = target_fig.axes[0], target_fig.axes[1]
        _clear_axes_artists(ax0)
        _clear_axes_artists(ax1)

    # ━━ Build per-segment style dict ━━
    segment_styles: dict[int, dict] = {}
    for segment_index in display_indices:
        if segment_index not in prepared_by_segment:
            continue
        is_active = has_active and segment_index == active_index
        style = _compute_segment_styles(has_active, is_active)
        style["color"] = p_get_segment_color(app, segment_index)
        style["has_active"] = has_active
        segment_styles[segment_index] = style

    with matplotlib.rc_context(MPL_RC):
        if full_rebuild:
            gs = target_fig.add_gridspec(1, 2, wspace=GRIDSPEC_WSPACE, left=GRIDSPEC_LEFT, right=GRIDSPEC_RIGHT, top=GRIDSPEC_TOP, bottom=GRIDSPEC_BOTTOM)
            ax0 = target_fig.add_subplot(gs[0])
            ax1 = target_fig.add_subplot(gs[1])

        _render_ej_plot(ax0, display_indices, prepared_by_segment, fit_by_segment, segment_styles)
        _render_tafel_plot(
            ax1,
            display_indices,
            prepared_by_segment,
            fit_by_segment,
            segment_styles,
            app._app_state.get("manual_fit_regions", {}),
        )

        # Labels, titles, legends
        active_fit = fit_by_segment.get(active_index) if has_active else None
        active_error = fit_error_by_segment.get(active_index) if has_active else None
        ax0.set_xlabel(ref_prepared.e_label, fontsize=FONTSIZE_LABEL)
        ax0.set_ylabel(ref_prepared.j_label, fontsize=FONTSIZE_LABEL)
        ax0.set_title(
            MULTI_SEGMENT_TITLE if len(display_indices) > 1 else f"第{ref_prepared.segment.index + 1}段电化学数据",
            fontsize=FONTSIZE_TITLE,
            color=TEXT_PRIMARY,
            pad=8,
        )
        ax0.grid(True)
        legend0 = _legend_if_needed(ax0)
        if not has_active:
            ax1.set_title("Tafel 拟合", fontsize=FONTSIZE_TITLE, color=TEXT_PRIMARY, pad=8)
        elif active_fit is None:
            title = f"Tafel 拟合失败 — 第{active_index + 1}段"
            if active_error:
                title = f"{title} | {active_error.strip()[:60]}"
            ax1.set_title(title, fontsize=FONTSIZE_TITLE, color=TEXT_PRIMARY, pad=8)
        else:
            ax1.set_title(
                f"当前分段第{active_index + 1}段 — {active_fit.slope_mv_per_dec:.2f} mV/dec, R²={active_fit.r2:.4f}",
                fontsize=FONTSIZE_TITLE,
                color=TEXT_PRIMARY,
                pad=8,
            )
        ax1.set_xlabel("log10(|j|)", fontsize=FONTSIZE_LABEL)
        ax1.set_ylabel(ref_prepared.tafel_y_label, fontsize=FONTSIZE_LABEL)
        ax1.grid(True)
        legend1 = _legend_if_needed(ax1)
        configure_static_legend(legend0)
        configure_static_legend(legend1)

        # Apply user-saved axis label overrides (double-click rename)
        overrides = app._app_state.get("axis_label_overrides", {})
        _apply_override(overrides, "single_ax0_xlabel", ax0.set_xlabel)
        _apply_override(overrides, "single_ax0_ylabel", ax0.set_ylabel)
        _apply_override(overrides, "single_ax0_title", ax0.set_title)
        _apply_override(overrides, "single_ax1_xlabel", ax1.set_xlabel)
        _apply_override(overrides, "single_ax1_ylabel", ax1.set_ylabel)
        _apply_override(overrides, "single_ax1_title", ax1.set_title)

        # Force recalc of data/view limits now so that capture_plot_view_state
        # (called after render_figure returns) gets correct autoscale values
        # instead of stale limits from reused axes or blank (0,1) defaults.
        ax0.relim(visible_only=True)
        ax0.autoscale_view()
        ax1.relim(visible_only=True)
        ax1.autoscale_view()
    return ax0, ax1


def _legend_if_needed(ax):
    handles, labels = ax.get_legend_handles_labels()
    if not any(label and not label.startswith("_") for label in labels):
        return None
    return ax.legend(fontsize=FONTSIZE_LEGEND, loc="upper right")


def enable_draggable_legend(legend) -> None:
    """Backward-compatible alias for static legend configuration."""
    if legend is None:
        return
    configure_static_legend(legend)


def configure_static_legend(legend, loc: str = "upper right") -> None:
    """Keep legends fixed across redraws and out of layout calculations."""
    if legend is None:
        return
    try:
        legend.set_draggable(False)
    except Exception:
        _log.debug("enable_draggable_legend: set_draggable failed", exc_info=True)
    try:
        legend.set_picker(True)
    except Exception:
        _log.debug("enable_draggable_legend: set_picker failed", exc_info=True)
    try:
        legend.set_in_layout(False)
    except Exception:
        _log.debug("configure_static_legend: set_in_layout failed", exc_info=True)
    try:
        legend.set_bbox_to_anchor(None)
    except Exception:
        try:
            legend._bbox_to_anchor = None
        except Exception:
            _log.debug("configure_static_legend: bbox reset failed", exc_info=True)
    _safe_set_legend_loc(legend, loc)


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


def axes_limits_from_view_state(
    view_state: dict | list | None,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if isinstance(view_state, list):
        view_state = view_state_from_legacy_limits(view_state)
    if not isinstance(view_state, dict):
        return []
    limits: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for axis_state in view_state.get("axes", []):
        if not isinstance(axis_state, dict):
            continue
        try:
            xlim = tuple(float(v) for v in axis_state.get("xlim", ()))
            ylim = tuple(float(v) for v in axis_state.get("ylim", ()))
        except (TypeError, ValueError):
            continue
        if len(xlim) == 2 and len(ylim) == 2:
            limits.append((xlim, ylim))
    return limits


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
        if not isinstance(axis_state, dict):
            continue
        try:
            xlim = axis_state.get("xlim")
            ylim = axis_state.get("ylim")
            if isinstance(xlim, (list, tuple)) and len(xlim) == 2:
                axis.set_xlim(float(xlim[0]), float(xlim[1]))
            if isinstance(ylim, (list, tuple)) and len(ylim) == 2:
                axis.set_ylim(float(ylim[0]), float(ylim[1]))
        except Exception:
            pass
        reset_legend_to_default(axis)


def capture_axes_limits(app: TafelAnalyzerApp) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    view_state = capture_plot_view_state(app, app.fig)
    if not view_state:
        return []
    return axes_limits_from_view_state(view_state)


def _autoscale_axis(axis) -> None:
    try:
        axis.autoscale(enable=True)
    except Exception:
        _log.debug("_autoscale_axis failed", exc_info=True)


def reset_legend_to_default(axis) -> None:
    legend = axis.get_legend()
    if legend is None:
        return
    configure_static_legend(legend, "upper right")


def reset_origin_view(app: TafelAnalyzerApp) -> None:
    """Reset both axes to data autoscale, update legend, and redraw.

    Always forces autoscale rather than relying on a previously-captured
    view-state dict, because set_xlim / set_ylim leave autoscale disabled
    after user zoom/pan, and draw_idle() will not override manual limits.
    """
    axes = app.fig.axes[:2]
    if len(axes) < 2:
        fallback = getattr(app, "_toolbar_home_original", None)
        if callable(fallback):
            fallback()
        return

    mode = "comparison" if app._app_state.get("active_chart_mode") == "comparison" else "single"
    if mode == "comparison":
        default_key = "compare_plot_default_view_state"
        current_key = "compare_plot_view_state"
    else:
        default_key = "single_plot_default_view_state"
        current_key = "single_plot_view_state"

    for ax in axes:
        reset_legend_to_default(ax)
        try:
            ax.autoscale(enable=True, tight=False)
        except Exception:
            _log.debug("reset_origin_view autoscale failed", exc_info=True)

    app._app_state[default_key] = capture_plot_view_state(app, app.fig)
    app._app_state[current_key] = capture_plot_view_state(app, app.fig)
    app.canvas.draw_idle()


def destroy_selector(app: TafelAnalyzerApp) -> None:
    selector = app._app_state.get("selector")
    if selector is not None:
        try:
            selector.set_active(False)
            selector.disconnect_events()
        except Exception:
            pass
        try:
            artists = list(getattr(selector, "artists", []) or [])
            for artist in artists:
                try:
                    artist.remove()
                except Exception:
                    pass
        except Exception:
            pass
    app._app_state["selector"] = None


def refresh_selector(app: TafelAnalyzerApp) -> None:
    manual_current = app._app_state.get("manual_mode", False)
    if hasattr(app, "state"):
        manual_current = app.state.interaction.manual_is_current(
            path=app.state.files.current_path,
            generation=app.state.operations.generation,
        )
    if not manual_current:
        destroy_selector(app)
        return
    ax_tafel = app._app_state.get("ax_tafel")
    if ax_tafel is None:
        destroy_selector(app)
        return

    # 复用已有 selector（同一 axes 上不销毁重建）
    existing = app._app_state.get("selector")
    if existing is not None:
        try:
            if getattr(existing, "ax", None) is ax_tafel:
                existing.set_active(True)
                return
        except Exception:
            pass

    destroy_selector(app)
    selector = RectangleSelector(
        ax_tafel,
        app.fitting.on_manual_select,
        useblit=True,
        button=[MouseButton.LEFT],
        minspanx=0.01,
        minspany=0.01,
        spancoords="data",
        interactive=False,
        props={"facecolor": "#60a5fa", "edgecolor": "#2563eb", "alpha": 0.18, "fill": True},
    )
    selector.set_active(True)
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
        preserve_view_state = current_or_saved_plot_view_state(app, "single")
    active_index = app.state.segments.active_index
    selected_indices = [int(index) for index in app.state.segments.selected_indices]
    display_indices = sorted(set(selected_indices))
    p_map = app.state.analysis.prepared_by_segment or {prepared.segment.index: prepared}
    f_map = app.state.analysis.fit_by_segment or ({prepared.segment.index: fit} if fit is not None else {})
    fe_map = dict(app.state.analysis.fit_error_by_segment)
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
    app._app_state["active_chart_mode"] = "single"
    app.canvas.draw_idle()
    refresh_selector(app)


def draw_placeholder(app: TafelAnalyzerApp) -> None:
    from core.theme import MPL_RC, TEXT_SECONDARY

    app.fig.clear()
    app._app_state["_chart_cache"] = None  # 占位图清空增量缓存
    with matplotlib.rc_context(MPL_RC):
        ax = app.fig.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "请选择数据文件并输入公式\n手动模式下可在右侧 Tafel 图框选区域",
            ha="center",
            va="center",
            fontsize=FONTSIZE_PLACEHOLDER,
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
    app._app_state["active_chart_mode"] = "single"
    app.canvas.draw_idle()
    refresh_selector(app)


# Avoid circular import - palette functions needed by render_figure
def p_get_segment_color(app, segment_index, file_path=None):
    from core.types import COMPARISON_COLORS

    color_map = app._app_state.get("segment_colors", {})
    return color_map.get(int(segment_index), COMPARISON_COLORS[int(segment_index) % len(COMPARISON_COLORS)])


