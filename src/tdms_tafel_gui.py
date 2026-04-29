"""向后兼容 facade — 所有 GUI 实现已迁移至 gui/ 子包。

新代码请直接从 gui 导入：
    from gui import TafelAnalyzerApp
    from gui.app import TafelAnalyzerApp
"""
from gui.app import DndCTk, TafelAnalyzerApp  # noqa: F401
from gui.theme import (  # noqa: F401
    ACCENT,
    ACCENT_HOVER,
    BG_LIGHT,
    BORDER_COLOR,
    CARD_BG,
    CYAN,
    CYAN_HOVER,
    MPL_RC,
    PLOT_FONT,
    PROCESSED_TAG,
    PURPLE,
    PURPLE_HOVER,
    SUCCESS,
    SUCCESS_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    WARNING_HOVER,
)
from gui.widgets import (  # noqa: F401
    RANGE_TEXT_PATTERN,
    make_combo_row as _make_combo_row,
    make_entry_row as _make_entry_row,
    make_section_label as _make_section_label,
    output_stem as _output_stem,
    parse_range_text as _parse_range_text,
    parse_segment_selection as _parse_segment_selection,
    path_labels as _path_labels,
    priority_key_to_label as _priority_key_to_label,
    priority_label_to_key as _priority_label_to_key,
    resolved_output_stem as _resolved_output_stem,
    segment_selection_text as _segment_selection_text,
    set_combo_values as _set_combo_values,
    set_entry_text as _set_entry_text,
    set_option_values as _set_option_values,
)
from gui.serialization import (  # noqa: F401
    fit_from_dict as _fit_from_dict,
    fit_to_dict as _fit_to_dict,
    prepared_from_dict as _prepared_from_dict,
    prepared_to_dict as _prepared_to_dict,
    segment_from_dict as _segment_from_dict,
    segment_to_dict as _segment_to_dict,
)
from gui.settings import APP_SETTINGS_PATH  # noqa: F401
from gui.settings import _resolve_app_settings_path  # noqa: F401


def build_app():
    """向后兼容包装器，返回 TafelAnalyzerApp 实例。"""
    return TafelAnalyzerApp()


if __name__ == "__main__":
    app = build_app()
    app.mainloop()
