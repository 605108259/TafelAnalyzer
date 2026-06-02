"""Activity bar — 48px vertical icon strip for panel switching."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from ui.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_SECONDARY
from ui.icons import line_icon


PANEL_FILES = 0
PANEL_COMPARISON = 1
PANEL_PALETTE = 2
PANEL_HISTORY = 3


class ActivityBar(QWidget):
    """48px vertical icon strip. 3 panels: files+segments, comparison, palette."""

    panel_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"""
            ActivityBar {{
                background: {BG_CARD};
                border-right: 1px solid #e2e8f0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        self._buttons: list[QPushButton] = []
        self._icon_names: list[str] = []

        for icon_name, panel_id, tooltip in [
            ("folder", PANEL_FILES, "文件与分段"),
            ("compare", PANEL_COMPARISON, "跨文件对比"),
            ("palette", PANEL_PALETTE, "配色方案"),
            ("history", PANEL_HISTORY, "历史项目"),
        ]:
            btn = QPushButton()
            btn.setToolTip(tooltip)
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(line_icon(icon_name, color=TEXT_SECONDARY, size=20))
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, pid=panel_id: self.set_active(pid) or self.panel_clicked.emit(pid))
            layout.addWidget(btn)
            self._buttons.append(btn)
            self._icon_names.append(icon_name)

        layout.addStretch()

    def _btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {ACCENT}; "
                f"border: none; border-radius: 8px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
        return (
            f"QPushButton {{ background: transparent; "
            f"border: none; border-radius: 8px; }}"
            f"QPushButton:hover {{ background: #f1f5f9; }}"
        )

    def set_active(self, panel_id: int) -> None:
        for idx, btn in enumerate(self._buttons):
            active = (idx == panel_id)
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
            color = "white" if active else TEXT_SECONDARY
            btn.setIcon(line_icon(self._icon_names[idx], color=color, size=20))
