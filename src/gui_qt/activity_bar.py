"""Activity bar — 48px vertical icon strip for panel switching."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon

from gui_qt.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_SECONDARY


PANEL_FILES = 0
PANEL_FORMULA = 1
PANEL_SEGMENTS = 2
PANEL_PARAMS = 3
PANEL_COMPARISON = 4


class ActivityBar(QWidget):
    """48px vertical icon strip. Click to switch side panels."""

    panel_clicked = Signal(int)   # panel index
    param_toggled = Signal(bool)  # param toolbar visibility

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
        self._active_index: int | None = None

        for icon_text, panel_id, tooltip in [
            ("📂", PANEL_FILES, "文件"),
            ("📐", PANEL_FORMULA, "公式"),
            ("📋", PANEL_SEGMENTS, "分段"),
            ("⚙", PANEL_PARAMS, "参数"),
        ]:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, pid=panel_id: self._on_click(pid))
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
        self._active_index = panel_id

    def _on_click(self, panel_id: int) -> None:
        if panel_id == self._active_index:
            # toggle collapse: emit -1 to signal collapse
            self.panel_clicked.emit(-1)
            self.set_active(-1)
            return
        self.set_active(panel_id)
        self.panel_clicked.emit(panel_id)

    def set_param_button_active(self, active: bool) -> None:
        if PANEL_PARAMS < len(self._buttons):
            btn = self._buttons[PANEL_PARAMS]
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
