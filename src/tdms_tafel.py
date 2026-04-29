"""向后兼容 facade — 所有实现已迁移至 core/ 子包。

新代码请直接从 core 导入：
    from core import TafelFit, auto_tafel_fit, read_data_all_channels, ...
    from core.cli import main
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

# CLI 入口保留在此，供 run_cli.py 调用
from core.cli import main
