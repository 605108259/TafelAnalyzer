"""Qt theme constants and QSS stylesheets."""

# ━━ Color palette ━━
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
SUCCESS = "#16a34a"
SUCCESS_HOVER = "#15803d"
WARNING = "#f59e0b"
WARNING_HOVER = "#d97706"
DANGER = "#dc2626"
PURPLE = "#7c3aed"
PURPLE_HOVER = "#6d28d9"
CYAN = "#0891b2"
CYAN_HOVER = "#0e7490"

BG_WINDOW = "#f8fafc"
BG_CARD = "#ffffff"
BG_HOVER = "#f1f5f9"
BG_SELECTED = "#eff6ff"
BORDER = "#e2e8f0"
BORDER_FOCUS = "#2563eb"

TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#64748b"
TEXT_DISABLED = "#94a3b8"
TEXT_ON_ACCENT = "#ffffff"

# ━━ QSS styles ━━

PANEL_STYLE = f"""
    QWidget#SidePanel {{
        background: {BG_CARD};
    }}
    QLabel#PanelTitle {{
        font-size: 13px;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        padding: 0px;
    }}
"""

BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
    }}
"""

ACCENT_BUTTON_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        color: {TEXT_ON_ACCENT};
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:disabled {{
        background: {TEXT_DISABLED};
        color: {BG_CARD};
    }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        background: {BG_CARD};
        color: {TEXT_PRIMARY};
        font-size: 12px;
    }}
    QLineEdit:focus {{
        border-color: {BORDER_FOCUS};
    }}
    QLineEdit:disabled {{
        background: {BG_HOVER};
        color: {TEXT_DISABLED};
    }}
"""

LIST_STYLE = f"""
    QListWidget {{
        border: none;
        background: transparent;
        outline: none;
    }}
    QListWidget::item {{
        border-radius: 6px;
        padding: 4px 8px;
        background: transparent;
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        spacing: 0px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 2px solid {BORDER};
        border-radius: 2px;
        background: {BG_CARD};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
        image: url(data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='white' d='M5.5 11.5L2 8l1.5-1.5L5.5 8.5 11 3l1.5 1.5z'/></svg>);
    }}
"""

# ━━ Compact toolbar styles ━━

TOOLBAR_STYLE = f"""
    QWidget#ToolBar {{
        background: {BG_CARD};
        border-bottom: 1px solid {BORDER};
    }}
"""

TOOLBAR_LABEL = f"""
    QLabel {{
        color: {TEXT_SECONDARY};
        font-size: 11px;
    }}
"""

SMALL_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: {TEXT_SECONDARY};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        color: {TEXT_PRIMARY};
    }}
"""

ICON_BUTTON_STYLE = f"""
    QToolButton {{
        border: none;
        border-radius: 6px;
        padding: 4px;
        background: transparent;
    }}
    QToolButton:hover {{
        background: {BG_HOVER};
    }}
    QToolButton:pressed {{
        background: {BG_HOVER};
    }}
"""

DANGER_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: {DANGER};
    }}
    QPushButton:hover {{
        background: #fee2e2;
    }}
"""

# ━━ FileSegmentPanel styles ━━

FILE_ITEM_STYLE = f"""
    QWidget#FileItem {{
        background: transparent;
    }}
    QWidget#FileItem:hover {{
        background: {BG_HOVER};
        border-radius: 6px;
    }}
"""

SEGMENT_ITEM_STYLE = f"""
    QWidget#SegmentItem {{
        background: transparent;
        border-radius: 6px;
    }}
    QWidget#SegmentItem:hover {{
        background: {BG_HOVER};
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        spacing: 0px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {BORDER};
        border-radius: 4px;
        background: {BG_CARD};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""

# ━━ Palette panel styles ━━

COLOR_SWATCH_STYLE = """
    QPushButton {{
        border: 2px solid white;
        border-radius: 8px;
    }}
    QPushButton:hover {{
        border-color: #2563eb;
    }}
"""

GRADIENT_PREVIEW_STYLE = f"""
    QWidget#GradientPreview {{
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
"""

STATUS_BAR_STYLE = f"""
    QLabel {{
        color: {TEXT_SECONDARY};
        font-size: 10px;
        padding: 2px 8px;
        background: {BG_CARD};
    }}
"""
