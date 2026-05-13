"""CLI 入口（由 run_cli.py 调用）。"""
from __future__ import annotations

import argparse
from pathlib import Path

from core.readers import read_data_all_channels
from core.fitting import auto_tafel_fit, build_segment_infos, prepare_series
from core.export import export_fit_npz, export_processed_txt, plot_tafel


def _build_output_stem(tdms_path: Path, segment_index: int, segment_count: int) -> str:
    if segment_count <= 1:
        return tdms_path.stem
    return f"{tdms_path.stem}_seg{segment_index + 1}"


def _process_one_file(
    tdms_path: Path,
    args: argparse.Namespace,
):
    channels = read_data_all_channels(tdms_path)
    segments = build_segment_infos(channels, args.potential_formula or None)
    prepared = prepare_series(
        channels,
        potential_formula=args.potential_formula,
        current_formula=args.current_formula,
        e_eq=float(args.e_eq),
        segment_index=max(0, int(args.segment) - 1),
        precomputed_segments=segments,
    )
    fit = auto_tafel_fit(
        prepared.eta,
        prepared.j,
        min_window=int(args.min_window),
        max_window=int(args.max_window) if args.max_window is not None else None,
        eta_range=args.eta_range,
        logj_range=args.logj_range,
        min_r2=float(args.min_r2) if args.min_r2 is not None else None,
        fit_priority=str(args.fit_priority),
    )
    segment_count = len(segments)
    out_dir = Path(args.out_dir) if args.out_dir is not None else tdms_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _build_output_stem(tdms_path, prepared.segment.index, segment_count)
    txt_path = export_processed_txt(out_dir / f"{stem}.txt", prepared, fit)
    fig_path = plot_tafel(out_dir / f"{stem}_tafel.png", prepared, fit)
    npz_path = export_fit_npz(out_dir / f"{stem}_tafel_fit.npz", prepared, fit)
    return txt_path, fig_path, npz_path, prepared, fit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tdms", type=Path, nargs="+", help="一个或多个数据文件路径 (tdms/txt/csv/xlsx/xls/cor)")
    parser.add_argument("--potential-formula", type=str, default="", help="电压公式，例如 -[Vgs]+0.23")
    parser.add_argument("--current-formula", type=str, default="", help="电流公式，例如 [Igs/area]/(2.4e-7+3)")
    parser.add_argument("--e-eq", type=float, default=0.0, help="平衡电位 E_eq，Tafel y = E - E_eq")
    parser.add_argument("--segment", type=int, default=1, help="要处理的分段序号，从 1 开始")
    parser.add_argument("--out-dir", type=Path, default=None, help="输出目录")
    parser.add_argument("--min-window", type=int, default=6, help="Tafel 最小窗口点数")
    parser.add_argument("--max-window", type=int, default=None, help="Tafel 最大窗口点数")
    parser.add_argument("--eta-range", type=lambda s: tuple(float(x) for x in s.split(",")), default=None)
    parser.add_argument("--logj-range", type=lambda s: tuple(float(x) for x in s.split(",")), default=None)
    parser.add_argument("--min-r2", type=float, default=0.95, help="最小 R2")
    parser.add_argument("--fit-priority", type=str, default="slope", choices=["slope", "r2"])
    args = parser.parse_args()

    for tdms_path in args.tdms:
        txt_path, fig_path, npz_path, prepared, fit = _process_one_file(tdms_path, args)
        print(f"文件: {tdms_path.name}")
        print(f"段号: 第{prepared.segment.index + 1}段")
        print(f"电压公式: {prepared.potential_formula}")
        print(f"电流公式: {prepared.current_formula}")
        print(f"E_eq: {prepared.e_eq}")
        print(f"已导出: {txt_path}")
        print(f"已绘图: {fig_path}")
        print(f"已保存拟合结果: {npz_path}")
        print(f"Tafel slope: {fit.slope_mv_per_dec:.3f} mV/dec, R2={fit.r2:.5f}")
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
