from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    TOOLBAR_STYLE, TOOLBAR_LABEL, INPUT_STYLE, ACCENT_BUTTON_STYLE,
    BG_CARD, BORDER, ACCENT, ACCENT_HOVER, SUCCESS, SUCCESS_HOVER,
    WARNING, WARNING_HOVER,
)


class ToolBar(QWidget):
    """Merged formula entry + parameter inputs + fit operations toolbar."""

    fit_clicked = Signal()
    manual_clicked = Signal()
    formulas_changed = Signal(str, str)  # potential, current
    params_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolBar")
        self.setFixedHeight(68)
        self.setStyleSheet(TOOLBAR_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(2)

        # Row 1: formula inputs
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        def add_formula(label_text: str, placeholder: str) -> QLineEdit:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(TOOLBAR_LABEL)
            row1.addWidget(lbl)
            entry = QLineEdit()
            entry.setPlaceholderText(placeholder)
            entry.setStyleSheet(INPUT_STYLE)
            entry.textChanged.connect(self._emit_formulas)
            row1.addWidget(entry, stretch=1)
            return entry

        self.potential_input = add_formula("电压:", "例如 -[Vgs]+0.23")
        self.current_input = add_formula("电流:", "例如 [Igs/area]/(2.4e-7+3)")
        outer.addLayout(row1)

        # Row 2: parameters + fit buttons
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        def add_param(label_text: str, width: int = 60, default: str = "") -> QLineEdit:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(TOOLBAR_LABEL)
            row2.addWidget(lbl)
            entry = QLineEdit()
            entry.setFixedWidth(width)
            entry.setStyleSheet(INPUT_STYLE)
            if default:
                entry.setText(default)
            entry.textChanged.connect(self._emit_params)
            row2.addWidget(entry)
            return entry

        self.entry_eeq = add_param("E_eq:", 50, "0")
        self.entry_window = add_param("窗口:", 55, "12-15")
        self.entry_eta = add_param("η:", 55)
        self.entry_logj = add_param("logj:", 55)
        self.entry_r2 = add_param("R²:", 45, "0.95")

        lbl_pri = QLabel("优先:")
        lbl_pri.setStyleSheet(TOOLBAR_LABEL)
        row2.addWidget(lbl_pri)
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["斜率更低优先", "R²优先"])
        self.combo_priority.setStyleSheet(
            f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 2px 6px; font-size: 11px; background: {BG_CARD}; }}"
        )
        self.combo_priority.currentTextChanged.connect(self._emit_params)
        row2.addWidget(self.combo_priority)

        row2.addStretch()

        btn_fit = QPushButton("▶ 拟合")
        btn_fit.setStyleSheet(ACCENT_BUTTON_STYLE.replace(ACCENT, SUCCESS).replace(ACCENT_HOVER, SUCCESS_HOVER))
        btn_fit.setCursor(Qt.PointingHandCursor)
        btn_fit.clicked.connect(self.fit_clicked.emit)
        row2.addWidget(btn_fit)

        btn_manual = QPushButton("🖱 手动")
        btn_manual.setStyleSheet(ACCENT_BUTTON_STYLE.replace(ACCENT, WARNING).replace(ACCENT_HOVER, WARNING_HOVER))
        btn_manual.setCursor(Qt.PointingHandCursor)
        btn_manual.clicked.connect(self.manual_clicked.emit)
        row2.addWidget(btn_manual)

        outer.addLayout(row2)

    def _emit_formulas(self):
        self.formulas_changed.emit(
            self.potential_input.text().strip(),
            self.current_input.text().strip(),
        )

    def _emit_params(self):
        self.params_changed.emit(self.get_params())

    def get_params(self) -> dict:
        return {
            "e_eq": self.entry_eeq.text().strip(),
            "window_range": self.entry_window.text().strip(),
            "eta_range": self.entry_eta.text().strip(),
            "logj_range": self.entry_logj.text().strip(),
            "min_r2": self.entry_r2.text().strip(),
            "fit_priority": self.combo_priority.currentText().strip(),
        }

    def get_formulas(self) -> tuple[str, str]:
        return self.potential_input.text().strip(), self.current_input.text().strip()

    def set_formulas(self, potential: str, current: str) -> None:
        self.potential_input.blockSignals(True)
        self.current_input.blockSignals(True)
        self.potential_input.setText(potential)
        self.current_input.setText(current)
        self.potential_input.blockSignals(False)
        self.current_input.blockSignals(False)

    def set_params(self, params: dict) -> None:
        mapping = {
            "e_eq": self.entry_eeq,
            "window_range": self.entry_window,
            "eta_range": self.entry_eta,
            "logj_range": self.entry_logj,
            "min_r2": self.entry_r2,
        }
        for key, entry in mapping.items():
            entry.blockSignals(True)
            val = params.get(key, "")
            if val:
                entry.setText(str(val))
            entry.blockSignals(False)
        if "fit_priority" in params:
            self.combo_priority.blockSignals(True)
            self.combo_priority.setCurrentText(params["fit_priority"])
            self.combo_priority.blockSignals(False)

    def set_enabled(self, enabled: bool) -> None:
        for w in [self.potential_input, self.current_input, self.entry_eeq,
                  self.entry_window, self.entry_eta, self.entry_logj, self.entry_r2,
                  self.combo_priority]:
            w.setEnabled(enabled)
