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
    }}
    QListWidget::item:hover {{
        background: {BG_HOVER};
    }}
    QListWidget::item:selected {{
        background: {BG_SELECTED};
        color: {TEXT_PRIMARY};
    }}
"""
