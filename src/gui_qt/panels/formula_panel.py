from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, INPUT_STYLE, PANEL_STYLE, TEXT_SECONDARY, TEXT_DISABLED, DANGER, BG_HOVER
)


class FormulaPanel(QWidget):
    """Side panel for potential/current formula input."""

    apply_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel("\U0001f4d0 公式")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Potential formula
        layout.addWidget(self._make_label("电压公式:"))
        self.potential_input = QLineEdit()
        self.potential_input.setPlaceholderText("例如 -[Vgs] + 0.23")
        self.potential_input.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.potential_input)

        # Current formula
        layout.addWidget(self._make_label("电流公式:"))
        self.current_input = QLineEdit()
        self.current_input.setPlaceholderText("例如 [Igs/area] / (2.4e-7 + 3)")
        self.current_input.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.current_input)

        # Error label (hidden by default)
        self.error_label = QLabel()
        self.error_label.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Apply button
        self.btn_apply = QPushButton("应用公式并拟合")
        self.btn_apply.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.btn_apply)

        # Channel list
        layout.addWidget(self._make_label("可用 Channel (点击插入):"))
        self.channel_browser = QTextBrowser()
        self.channel_browser.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid #e2e8f0; border-radius: 4px; "
            f"background: {BG_HOVER}; color: {TEXT_SECONDARY}; font-size: 12px; padding: 8px; }}"
        )
        self.channel_browser.setOpenLinks(False)
        self.channel_browser.anchorClicked.connect(self._on_channel_clicked)
        layout.addWidget(self.channel_browser, stretch=1)

        self._active_input = self.potential_input  # track which input to insert into

        # Focus tracking
        self.potential_input.installEventFilter(self)
        self.current_input.installEventFilter(self)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def set_channels(self, channel_names: list[str]) -> None:
        html = " ".join(
            f'<a href="ch:{name}" style="color:#2563eb;text-decoration:none;">[{name}]</a>'
            for name in channel_names
        )
        self.channel_browser.setHtml(html)

    def _on_channel_clicked(self, url):
        name = url.toString().replace("ch:", "")
        cursor = self._active_input.cursorPosition()
        current = self._active_input.text()
        self._active_input.setText(current[:cursor] + f"[{name}]" + current[cursor:])
        self._active_input.setFocus()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn:
            if obj is self.potential_input:
                self._active_input = self.potential_input
            elif obj is self.current_input:
                self._active_input = self.current_input
        return super().eventFilter(obj, event)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def hide_error(self) -> None:
        self.error_label.setVisible(False)

    def get_formulas(self) -> tuple[str, str]:
        return self.potential_input.text().strip(), self.current_input.text().strip()
