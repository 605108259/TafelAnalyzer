from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, ACCENT, ACCENT_HOVER, BG_CARD, BORDER, TEXT_SECONDARY
)


class ChartToolBar(QWidget):
    """Custom toolbar below the chart: zoom, pan, manual select, export."""

    home_clicked = Signal()
    zoom_in_clicked = Signal()
    zoom_out_clicked = Signal()
    pan_clicked = Signal()
    manual_clicked = Signal()
    save_image_clicked = Signal()
    copy_clipboard_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            ChartToolBar {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self._tool_btns: dict[str, QPushButton] = {}
        self._active_tool: str | None = None

        for icon, tooltip, signal in [
            ("↺", "重置视图", self.home_clicked),
            ("🔍+", "放大", self.zoom_in_clicked),
            ("🔍-", "缩小", self.zoom_out_clicked),
            ("✋", "平移", self.pan_clicked),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

        layout.addWidget(self._sep())

        self.btn_manual = QPushButton("▭ 框选拟合")
        self.btn_manual.setToolTip("手动框选 Tafel 拟合区域")
        self.btn_manual.setCheckable(True)
        self.btn_manual.setCursor(Qt.PointingHandCursor)
        self.btn_manual.setStyleSheet(self._tool_btn_style(False))
        self.btn_manual.clicked.connect(self._on_manual_click)
        layout.addWidget(self.btn_manual)

        layout.addWidget(self._sep())

        for icon, tooltip, signal in [
            ("💾 保存图片", "保存图表为 PNG", self.save_image_clicked),
            ("📋 复制", "复制到剪贴板", self.copy_clipboard_clicked),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

        layout.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _sep(self) -> QLabel:
        s = QLabel("|")
        s.setStyleSheet(f"color: {BORDER}; font-size: 14px; padding: 0 2px;")
        return s

    def _tool_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {ACCENT}; color: white; "
                f"border: none; border-radius: 6px; padding: 4px 12px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
        return BUTTON_STYLE

    def _on_manual_click(self) -> None:
        active = self.btn_manual.isChecked()
        self.btn_manual.setStyleSheet(self._tool_btn_style(active))
        self.manual_clicked.emit()

    def set_manual_mode(self, active: bool) -> None:
        self.btn_manual.setChecked(active)
        self.btn_manual.setStyleSheet(self._tool_btn_style(active))

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
