from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QToolButton,
)
from PySide6.QtCore import Signal, Qt

from ui.theme import (
    TOOLBAR_STYLE, TOOLBAR_LABEL, INPUT_STYLE, ACCENT_BUTTON_STYLE,
    BG_CARD, BORDER, ACCENT, ACCENT_HOVER, SUCCESS, SUCCESS_HOVER,
    WARNING, WARNING_HOVER, ICON_BUTTON_STYLE, TEXT_PRIMARY,
)


class ToolBar(QWidget):
    """Merged formula entry + parameter inputs + fit operations toolbar."""

    fit_clicked = Signal()
    manual_clicked = Signal()
    save_image_clicked = Signal()
    nav_home_clicked = Signal()
    nav_back_clicked = Signal()
    nav_forward_clicked = Signal()
    nav_zoom_clicked = Signal()
    nav_pan_clicked = Signal()
    nav_cancel_clicked = Signal()
    formulas_changed = Signal(str, str)  # potential, current
    params_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolBar")
        self.setFixedHeight(68)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(TOOLBAR_STYLE)

        from ui.icons import line_icon

        self._tool_buttons: dict[str, QToolButton] = {}
        self._action_buttons: dict[str, QToolButton] = {}
        self._tool_actions: dict[str, Any] = {}
        self._active_tool: str | None = None

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

        btn_fit = QPushButton("▶ 拟合")
        btn_fit.setStyleSheet(ACCENT_BUTTON_STYLE.replace(ACCENT, SUCCESS).replace(ACCENT_HOVER, SUCCESS_HOVER))
        btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fit.clicked.connect(self.fit_clicked.emit)
        row2.addWidget(btn_fit)

        row2.addStretch()

        def _toggle_btn(name: str, tooltip: str, signal: Any) -> QToolButton:
            btn = QToolButton()
            btn.setIcon(line_icon(name, color=TEXT_PRIMARY, size=16))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet(ICON_BUTTON_STYLE +
                f"QToolButton:checked {{ background: #2563eb; border-radius: 4px; padding: 2px; }}"
                f"QToolButton:checked:hover {{ background: #1d4ed8; }}")
            btn.clicked.connect(lambda checked, n=name, s=signal: self._on_tool_toggled(n, checked, s))
            self._tool_buttons[name] = btn
            self._tool_actions[name] = signal
            return btn

        def _action_btn(name: str, tooltip: str, signal: Any) -> QToolButton:
            btn = QToolButton()
            btn.setIcon(line_icon(name, color=TEXT_PRIMARY, size=16))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(ICON_BUTTON_STYLE)
            btn.clicked.connect(signal.emit)
            self._action_buttons[name] = btn
            return btn

        _toggle_btn("select", "手动框选", self.manual_clicked)
        _toggle_btn("zoom", "缩放", self.nav_zoom_clicked)
        _toggle_btn("pan", "平移", self.nav_pan_clicked)

        _action_btn("home", "复位", self.nav_home_clicked)
        _action_btn("back", "后退", self.nav_back_clicked)
        _action_btn("forward", "前进", self.nav_forward_clicked)

        save_btn = QToolButton()
        save_btn.setIcon(line_icon("save", color=TEXT_PRIMARY, size=16))
        save_btn.setToolTip("保存图片")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(ICON_BUTTON_STYLE)
        save_btn.clicked.connect(self.save_image_clicked.emit)

        row2.addWidget(save_btn)
        for name in ["select", "zoom", "pan"]:
            row2.addWidget(self._tool_buttons[name])
        for name in ["home", "back", "forward"]:
            row2.addWidget(self._action_buttons[name])

        outer.addLayout(row2)

    def _on_tool_toggled(self, name: str, checked: bool, signal: Any) -> None:
        if checked:
            for n, btn in self._tool_buttons.items():
                if n != name:
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
            self._active_tool = name
            signal.emit()
        else:
            self._active_tool = None
            self.nav_cancel_clicked.emit()

    def clear_nav_mode(self) -> None:
        for btn in self._tool_buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self._active_tool = None

    def active_tool(self) -> str | None:
        return self._active_tool

    def set_active_tool(self, name: str | None) -> None:
        if name is None:
            self.clear_nav_mode()
        elif name in self._tool_buttons:
            self._tool_buttons[name].setChecked(True)
            self._on_tool_toggled(name, True, self._tool_actions[name])

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
            if key in params:
                entry.setText(str(params.get(key, "")))
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
