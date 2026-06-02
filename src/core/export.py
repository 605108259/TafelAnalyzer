"""导出函数：txt / npz / 图表。"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from core.types import PreparedSeries, TafelFit
from core.utils import apply_matplotlib_cjk


def export_txt(path: Path, channels: dict[str, np.ndarray]) -> Path:
    if not channels:
        raise ValueError("没有可导出的 channel")
    names = list(channels.keys())
    lengths = [int(np.asarray(channels[name]).size) for name in names]
    n = min(lengths)
    arr = np.column_stack([np.asarray(channels[name]).reshape(-1)[:n] for name in names])
    np.savetxt(
        path,
        arr,
        delimiter="\t",
        header="\t".join(names),
        comments="",
        fmt="%.10g",
        encoding="utf-8-sig",
    )
    return path


def export_processed_txt(path: Path, prepared: PreparedSeries,
                         fit: TafelFit | None) -> Path:
    n = min(prepared.raw_e.size, prepared.raw_j.size, prepared.e.size, prepared.j.size)
    fit_x = np.full(n, np.nan, dtype=float)
    fit_y = np.full(n, np.nan, dtype=float)
    line_x = np.full(n, np.nan, dtype=float)
    line_y = np.full(n, np.nan, dtype=float)
    if fit is not None:
        selected_x = fit.x_log10_j[fit.selected_mask]
        selected_y = fit.y_e[fit.selected_mask]
        selected_count = min(n, selected_x.size, selected_y.size)
        fit_x[:selected_count] = selected_x[:selected_count]
        fit_y[:selected_count] = selected_y[:selected_count]
        if selected_x.size >= 2:
            line_count = max(2, n)
            sampled_x = np.linspace(float(selected_x.min()), float(selected_x.max()), line_count)
            sampled_y = fit.slope_v_per_dec * sampled_x + fit.intercept_v
            line_x[:line_count] = sampled_x[:n]
            line_y[:line_count] = sampled_y[:n]
    export_array = np.column_stack(
        [
            prepared.raw_e[:n],
            prepared.raw_j[:n],
            prepared.e[:n],
            prepared.j[:n],
            fit_x,
            fit_y,
            line_x,
            line_y,
        ]
    )
    header = "\t".join(
        [
            "原始电压",
            "原始电流",
            "处理后的电压",
            "处理后的电流",
            "用于拟合tafel点的横坐标",
            "用于拟合tafel点的纵坐标",
            "拟合直线的横坐标",
            "拟合直线的纵坐标",
        ]
    )
    np.savetxt(
        path,
        export_array,
        delimiter="\t",
        header=header,
        comments="",
        fmt="%.10g",
        encoding="utf-8-sig",
    )
    return path


def export_fit_npz(path: Path, prepared: PreparedSeries,
                    fit: TafelFit | None) -> Path:
    kwargs: dict = dict(
        raw_e=prepared.raw_e,
        raw_j=prepared.raw_j,
        processed_e=prepared.e,
        processed_j=prepared.j,
        overpotential=prepared.eta,
        potential_channel=prepared.potential_channel,
        current_channel=prepared.current_channel,
        potential_formula=prepared.potential_formula,
        current_formula=prepared.current_formula,
        e_eq=prepared.e_eq,
        segment_index=prepared.segment.index + 1,
    )
    if fit is not None:
        kwargs.update(
            x_log10_j=fit.x_log10_j,
            y_e=fit.y_e,
            selected_mask=fit.selected_mask,
            source_indices=fit.source_indices,
            slope_v_per_dec=fit.slope_v_per_dec,
            slope_mv_per_dec=fit.slope_mv_per_dec,
            intercept_v=fit.intercept_v,
            r2=fit.r2,
            fit_mode=fit.mode,
        )
    np.savez(path, **kwargs)
    return path


def plot_tafel(out_png: Path, prepared: PreparedSeries, fit: TafelFit | None,
               axis_overrides: dict | None = None) -> Path:
    import matplotlib
    from matplotlib.figure import Figure

    if axis_overrides is None:
        axis_overrides = {}
    apply_matplotlib_cjk(matplotlib)
    fig = Figure(figsize=(12, 4.8))
    ax0, ax1 = fig.subplots(1, 2)
    ax0.plot(prepared.e, prepared.j, marker="o", markersize=3.5, linewidth=1.1, label="处理后")
    if fit is not None:
        fit_indices = fit.source_indices[fit.selected_mask]
        if fit_indices.size:
            # Clip to prepared data bounds (indices may reference original full range)
            n_prepared = min(prepared.e.size, prepared.j.size)
            valid_idx = fit_indices[(fit_indices >= 0) & (fit_indices < n_prepared)]
            if valid_idx.size:
                ax0.scatter(prepared.e[valid_idx], prepared.j[valid_idx], s=24, label="拟合点")
    ax0.set_xlabel(axis_overrides.get("single_ax0_xlabel", prepared.e_label))
    ax0.set_ylabel(axis_overrides.get("single_ax0_ylabel", prepared.j_label))
    ax0.set_title(f"第{prepared.segment.index + 1}段电化学数据")
    ax0.grid(True, alpha=0.3)
    ax0.legend()

    if fit is not None:
        x = fit.x_log10_j
        y = fit.y_e
        mask = fit.selected_mask
        ax1.scatter(x[~mask], y[~mask], s=18, alpha=0.45, label="未选")
        ax1.scatter(x[mask], y[mask], s=24, label="拟合点")
        xs = x[mask]
        if xs.size >= 2:
            x_line = np.linspace(float(xs.min()), float(xs.max()), 80)
            y_line = fit.slope_v_per_dec * x_line + fit.intercept_v
            ax1.plot(x_line, y_line, linewidth=2, label=f"{fit.mode} 拟合")
        ax1.set_title(f"Tafel slope={fit.slope_mv_per_dec:.2f} mV/dec, R²={fit.r2:.4f}")
    else:
        ax1.set_title("Tafel 拟合 (无结果)")
    ax1.set_xlabel(axis_overrides.get("single_ax1_xlabel", "log10(|j|)"))
    ax1.set_ylabel(axis_overrides.get("single_ax1_ylabel", prepared.tafel_y_label))
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    fig.clear()
    return out_png
