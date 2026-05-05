"""Activity bar — 48px vertical icon strip for panel switching."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from ui.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_SECONDARY


PANEL_FILES = 0
PANEL_COMPARISON = 1
PANEL_PALETTE = 2


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

        for icon_text, panel_id, tooltip in [
            ("📂", PANEL_FILES, "文件与分段"),
            ("📊", PANEL_COMPARISON, "跨文件对比"),
            ("🎨", PANEL_PALETTE, "配色方案"),
        ]:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, pid=panel_id: self.set_active(pid) or self.panel_clicked.emit(pid))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

    def _btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {ACCENT}; color: white; "
                f"border: none; border-radius: 8px; font-size: 18px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: none; border-radius: 8px; font-size: 18px; }}"
            f"QPushButton:hover {{ background: #f1f5f9; }}"
        )

    def set_active(self, panel_id: int) -> None:
        for idx, btn in enumerate(self._buttons):
            active = (idx == panel_id)
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
