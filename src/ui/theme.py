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
        background: transparent;
        padding: 0px;
    }}
    QListWidget::item:selected {{
        background: {BG_SELECTED};
        border-radius: 4px;
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


# ━━ Custom checkbox widget ━━

from PySide6.QtWidgets import QAbstractButton
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath


class CheckmarkBox(QAbstractButton):
    """Custom checkbox that paints a ✓ with QPainter (no QSS image needed)."""

    stateChanged = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(18, 18)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._toggle)

    def _toggle(self):
        self._checked = not self._checked
        self.stateChanged.emit(self._checked)
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self.update()

    def sizeHint(self):
        return self.minimumSize()

    def minimumSizeHint(self):
        return self.minimumSize()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, w, h = 1, 1, self.width() - 2, self.height() - 2
        if self._checked:
            p.setBrush(QColor(ACCENT_HOVER))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, w, h, 3, 3)
            # White checkmark — bold, slightly larger
            pen = QPen(QColor("white"))
            pen.setWidthF(2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(x + w * 0.20, y + h * 0.52)
            path.lineTo(x + w * 0.42, y + h * 0.76)
            path.lineTo(x + w * 0.80, y + h * 0.24)
            p.drawPath(path)
        else:
            p.setBrush(QColor(BG_CARD))
            pen = QPen(QColor(TEXT_DISABLED))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.drawRoundedRect(x, y, w, h, 3, 3)
        p.end()
