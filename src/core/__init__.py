"""Tafel Analyzer 核心逻辑层。

子模块:
- types:   数据类（TafelFit, SegmentInfo 等）和常量
- utils:   工具函数（字体、channel 解析等）
- readers: 文件读取（TDMS / COR / 表格）
- formula: 公式解析与求值
- fitting: Tafel 拟合 + 自动分段
- export:  导出（txt / npz / 图片 / 缓存）
- cli:     CLI 入口
"""

from core.types import (
    CHANNEL_REF_PATTERN,
    COMPARISON_COLORS,
    COR_DEFAULT_HEADERS,
    CURRENT_PREFERRED_NAMES,
    POTENTIAL_PREFERRED_NAMES,
    ComparisonItem,
    FormulaResult,
    PreparedSeries,
    SegmentInfo,
    TafelFit,
    _normalize_optional_range,
)
from core.utils import (
    _channel_basename,
    apply_matplotlib_cjk,
    get_cjk_font_name,
    pick_channel_name,
    resolve_channel_name,
)
from core.readers import (
    read_corrw_cor_channels,
    read_data_all_channels,
    read_table_channels,
    read_tdms_all_channels,
)
from core.formula import (
    evaluate_formula,
    normalize_formula,
)
from core.fitting import (
    _best_window_fit,
    _expand_region,
    _fit_from_selected,
    _linear_fit,
    _prepare_xy,
    _r2_score,
    _window_rank,
    auto_tafel_fit,
    build_segment_infos,
    manual_tafel_fit,
    prepare_series,
)
from core.export import (
    export_fit_npz,
    export_processed_txt,
    export_txt,
    plot_tafel,
)

# 注意：cli.main 未在此处导入，因为它和 parse_args 相关逻辑由 run_cli.py 调用
