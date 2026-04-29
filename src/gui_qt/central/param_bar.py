from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QRegularExpressionValidator

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, INPUT_STYLE, TEXT_SECONDARY, BG_CARD, BORDER,
)


class RangeValidator(QRegularExpressionValidator):
    """Validates 'min-max' format like '12-15' or '-3--1'."""
    def __init__(self, parent=None):
        super().__init__(
            r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*-\s*"
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*$",
            parent,
        )


class FloatValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        super().__init__(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*$", parent)


class ParamToolBar(QWidget):
    """Fixed toolbar above chart with fitting parameters."""

    fit_clicked = Signal()
    parameters_changed = Signal(dict)  # {param_name: value}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            ParamToolBar {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        def add_param(label: str, width: int = 80) -> QLineEdit:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(lbl)
            entry = QLineEdit()
            entry.setFixedWidth(width)
            entry.setStyleSheet(INPUT_STYLE)
            layout.addWidget(entry)
            return entry

        self.entry_eeq = add_param("E_eq:")
        self.entry_window = add_param("窗口:", 70)
        self.entry_eta = add_param("η:", 70)
        self.entry_logj = add_param("logj:", 70)
        self.entry_r2 = add_param("R²:", 60)

        # Fit priority combo
        lbl = QLabel("优先:")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(lbl)
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["斜率更低优先", "R²优先"])
        self.combo_priority.setStyleSheet(
            f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 12px; }}"
        )
        layout.addWidget(self.combo_priority)

        layout.addStretch()

        # Run button
        self.btn_fit = QPushButton("▶ 自动拟合")
        self.btn_fit.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_fit.setCursor(Qt.PointingHandCursor)
        self.btn_fit.clicked.connect(self.fit_clicked.emit)
        layout.addWidget(self.btn_fit)

    def set_defaults(self, defaults: dict) -> None:
        mapping = {
            "e_eq": self.entry_eeq,
            "window_range": self.entry_window,
            "eta_range": self.entry_eta,
            "logj_range": self.entry_logj,
            "min_r2": self.entry_r2,
        }
        for key, entry in mapping.items():
            val = defaults.get(key, "")
            if val:
                entry.setText(str(val))

    def get_params(self) -> dict:
        return {
            "e_eq": self.entry_eeq.text().strip(),
            "window_range": self.entry_window.text().strip(),
            "eta_range": self.entry_eta.text().strip(),
            "logj_range": self.entry_logj.text().strip(),
            "min_r2": self.entry_r2.text().strip(),
            "fit_priority": self.combo_priority.currentText().strip(),
        }

    def set_enabled(self, enabled: bool) -> None:
        for widget in [self.entry_eeq, self.entry_window, self.entry_eta,
                       self.entry_logj, self.entry_r2, self.combo_priority, self.btn_fit]:
            widget.setEnabled(enabled)
