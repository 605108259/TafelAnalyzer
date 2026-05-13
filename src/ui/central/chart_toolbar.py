from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from ui.theme import (
    BG_CARD, BORDER, TEXT_SECONDARY, BG_HOVER,
)
from ui.central.chart_widget import ChartArea


class ChartToolBar(QWidget):
    """Custom matplotlib toolbar: zoom, pan, home, manual, save."""

    save_image_clicked = Signal()
    manual_clicked = Signal()

    def __init__(self, chart_area: ChartArea, parent=None):
        super().__init__(parent)
        self._chart = chart_area
        self._nav = chart_area._nav_toolbar
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

        def make_btn(text: str, tooltip: str, callback) -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 4px; font-size: 14px; "
                f"color: {TEXT_SECONDARY}; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; color: #0f172a; }}"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            return btn

        layout.addWidget(make_btn("🏠", "复位", self._nav.home))
        layout.addWidget(make_btn("←", "后退", self._nav.back))
        layout.addWidget(make_btn("→", "前进", self._nav.forward))
        layout.addWidget(make_btn("🔍+", "放大", self._nav.zoom))
        layout.addWidget(make_btn("✋", "平移", self._nav.pan))
        layout.addWidget(make_btn("🖱", "手动框选", self.manual_clicked.emit))

        layout.addStretch()

        btn_save = QPushButton("💾")
        btn_save.setToolTip("保存图片")
        btn_save.setFixedSize(28, 28)
        btn_save.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 4px; font-size: 14px; "
            f"color: {TEXT_SECONDARY}; }}"
            f"QPushButton:hover {{ background: {BG_HOVER}; color: #0f172a; }}"
        )
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.save_image_clicked.emit)
        layout.addWidget(btn_save)
