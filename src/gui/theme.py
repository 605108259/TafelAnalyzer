"""UI 主题常量（颜色/样式）。"""

from core.utils import get_cjk_font_name

ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
BG_LIGHT = "#f5f7fb"
CARD_BG = "#ffffff"
TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#475569"
BORDER_COLOR = "#d7deea"
SUCCESS = "#16a34a"
SUCCESS_HOVER = "#15803d"
WARNING = "#f59e0b"
WARNING_HOVER = "#d97706"
CYAN = "#0891b2"
CYAN_HOVER = "#0e7490"
PURPLE = "#7c3aed"
PURPLE_HOVER = "#6d28d9"
PROCESSED_TAG = "✓ 已处理"

# 分段面板按钮颜色
CHECKED_BG = "#dbeafe"
UNCHECKED_BG = "#f1f5f9"
CHECKED_HOVER_BG = "#bfdbfe"
UNCHECKED_HOVER_BG = "#e2e8f0"
ACTIVE_BTN_BG = ACCENT
INACTIVE_SELECTED_BG = "#eff6ff"
INACTIVE_UNSELECTED_BG = "#f8fafc"
INACTIVE_SELECTED_HOVER = "#dbeafe"
INACTIVE_UNSELECTED_HOVER = "#eef2ff"
ACTIVE_TEXT_COLOR = "#ffffff"
SEGMENT_BTN_FONT_COLOR = TEXT_PRIMARY

# 组件颜色
COMBO_BUTTON_COLOR = "#e2e8f0"
COMBO_BUTTON_HOVER = "#cbd5e1"
COMBO_DROPDOWN_BG = "#ffffff"
COMBO_DROPDOWN_HOVER = "#eff6ff"
ENTRY_BG = "#ffffff"

_PLOT_FONT_CACHE = None


def get_plot_font() -> str:
    global _PLOT_FONT_CACHE
    if _PLOT_FONT_CACHE is None:
        _PLOT_FONT_CACHE = get_cjk_font_name()
    return _PLOT_FONT_CACHE


PLOT_FONT = get_plot_font()


MPL_RC = {
    "figure.facecolor": CARD_BG,
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": TEXT_PRIMARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "text.color": TEXT_PRIMARY,
    "grid.color": "#e2e8f0",
    "grid.alpha": 0.85,
    "legend.facecolor": "#ffffff",
    "legend.edgecolor": "#dbe4ee",
    "legend.labelcolor": TEXT_PRIMARY,
    "font.family": [get_plot_font()],
    "font.sans-serif": [get_plot_font(), "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 10,
}
