from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, BG_CARD, BORDER, TEXT_SECONDARY, ACCENT, BG_HOVER,
)


class ChartToolBar(QWidget):
    """Custom matplotlib toolbar: zoom, pan, home, manual, save."""

    zoom_clicked = Signal()
    pan_clicked = Signal()
    home_clicked = Signal()
    save_image_clicked = Signal()
    manual_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            ChartToolBar {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        def make_btn(text: str, tooltip: str, signal: Signal) -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 4px; font-size: 14px; "
                f"color: {TEXT_SECONDARY}; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; color: #0f172a; }}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            return btn

        layout.addWidget(make_btn("🏠", "复位", self.home_clicked))
        layout.addWidget(make_btn("←", "后退", self.home_clicked))
        layout.addWidget(make_btn("→", "前进", self.home_clicked))
        layout.addWidget(make_btn("🔍+", "放大", self.zoom_clicked))
        layout.addWidget(make_btn("🔍-", "缩小", self.zoom_clicked))
        layout.addWidget(make_btn("✋", "平移", self.pan_clicked))
        layout.addWidget(make_btn("🖱", "手动框选", self.manual_clicked))

        layout.addStretch()

        layout.addWidget(make_btn("💾", "保存图片", self.save_image_clicked))
