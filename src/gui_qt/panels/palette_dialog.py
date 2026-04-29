from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QColorDialog, QFrame,
    QScrollArea, QWidget, QGridLayout, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from gui_qt.theme import (
    ACCENT, ACCENT_HOVER, BG_WINDOW, BG_CARD, BG_HOVER, BG_SELECTED,
    BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ON_ACCENT,
    SUCCESS, SUCCESS_HOVER, DANGER, BUTTON_STYLE, ACCENT_BUTTON_STYLE,
)
from gui import palette as p

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class PaletteSchemeManager(QDialog):
    """调色板方案管理对话框。"""

    schemes_updated = Signal()

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("调色板方案管理")
        self.setMinimumSize(860, 620)
        self.resize(860, 620)
        self.setStyleSheet(f"QDialog {{ background: {BG_WINDOW}; }}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Left panel: scheme list
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet(f"QWidget {{ background: {BG_CARD}; border-radius: 8px; }}")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)

        left_layout.addWidget(self._title_label("调色板方案"))

        # Add scheme row
        add_row = QHBoxLayout()
        self.entry_new = QLineEdit()
        self.entry_new.setPlaceholderText("输入新方案名")
        self.entry_new.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 12px; }}"
        )
        add_row.addWidget(self.entry_new)

        btn_add = QPushButton("新增")
        btn_add.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_add.clicked.connect(self._add_scheme)
        add_row.addWidget(btn_add)
        left_layout.addLayout(add_row)

        self.scheme_list = QListWidget()
        self.scheme_list.setStyleSheet(
            f"QListWidget {{ border: none; outline: none; }}"
            f"QListWidget::item {{ padding: 8px; border-radius: 6px; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        self.scheme_list.currentItemChanged.connect(self._on_scheme_selected)
        left_layout.addWidget(self.scheme_list, stretch=1)

        btn_delete = QPushButton("删除当前方案")
        btn_delete.setStyleSheet(
            f"QPushButton {{ background: #fee2e2; color: {DANGER}; "
            f"border: none; border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: #fecaca; }}"
        )
        btn_delete.clicked.connect(self._delete_scheme)
        left_layout.addWidget(btn_delete)

        # Right panel: color grid
        right = QWidget()
        right.setStyleSheet(f"QWidget {{ background: {BG_CARD}; border-radius: 8px; }}")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)

        self.scheme_title = QLabel("颜色设置")
        self.scheme_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};"
        )
        right_layout.addWidget(self.scheme_title)

        self.color_scroll = QScrollArea()
        self.color_scroll.setWidgetResizable(True)
        self.color_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }}"
        )
        self.color_grid_widget = QWidget()
        self.color_grid = QGridLayout(self.color_grid_widget)
        self.color_grid.setSpacing(6)
        self.color_scroll.setWidget(self.color_grid_widget)
        right_layout.addWidget(self.color_scroll, stretch=1)

        # Bottom: apply buttons
        btn_row = QHBoxLayout()
        btn_apply_current = QPushButton("应用方案到当前分段")
        btn_apply_current.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_apply_current.clicked.connect(self._apply_to_current)
        btn_row.addWidget(btn_apply_current)

        btn_apply_compare = QPushButton("应用方案到对比")
        btn_apply_compare.setStyleSheet(BUTTON_STYLE)
        btn_apply_compare.clicked.connect(self._apply_to_comparison)
        btn_row.addWidget(btn_apply_compare)

        btn_add_slot = QPushButton("+ 新增颜色位")
        btn_add_slot.setStyleSheet(BUTTON_STYLE)
        btn_add_slot.clicked.connect(self._add_color_slot)
        btn_row.addWidget(btn_add_slot)
        right_layout.addLayout(btn_row)

        layout.addWidget(left)
        layout.addWidget(right, stretch=1)

        self._populate_scheme_list()

    def _title_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        return lbl

    def _populate_scheme_list(self) -> None:
        self.scheme_list.clear()
        schemes = self.app._app_state.get("palette_schemes", {})
        for name in schemes:
            item = QListWidgetItem(name)
            self.scheme_list.addItem(item)
        if self.scheme_list.count() > 0:
            self.scheme_list.setCurrentRow(0)

    def _on_scheme_selected(self, current, previous) -> None:
        if current is None:
            return
        name = current.text()
        self._render_colors(name)

    def _render_colors(self, scheme_name: str) -> None:
        # Clear grid
        while self.color_grid.count():
            w = self.color_grid.takeAt(0).widget()
            if w:
                w.deleteLater()

        self.scheme_title.setText(f'颜色设置: 当前方案 "{scheme_name}"')
        colors = p.get_palette_scheme_colors(
            self.app, scheme_name, include_defaults=True
        )

        hex_validator = QRegularExpressionValidator(
            QRegularExpression(r"^#[0-9a-fA-F]{6}$")
        )

        for idx in sorted(colors):
            color = colors[idx]
            row = idx

            # Label
            lbl = QLabel(f"第{idx + 1}段")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            self.color_grid.addWidget(lbl, row, 0)

            # Preview button
            preview = QPushButton()
            preview.setFixedSize(28, 24)
            preview.setStyleSheet(
                f"QPushButton {{ background: {color}; border: none; border-radius: 4px; }}"
                f"QPushButton:hover {{ border: 2px solid {ACCENT}; }}"
            )
            preview.clicked.connect(lambda checked, idx=idx: self._pick_color(idx))
            self.color_grid.addWidget(preview, row, 1)

            # Hex input
            entry = QLineEdit(color)
            entry.setFixedWidth(120)
            entry.setStyleSheet(
                f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; "
                f"padding: 4px 8px; font-size: 12px; }}"
                f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
            )
            entry.setValidator(hex_validator)
            entry.editingFinished.connect(
                lambda e=entry, idx=idx: self._apply_hex(idx, e.text())
            )
            self.color_grid.addWidget(entry, row, 2)

            # Apply button
            apply_btn = QPushButton("应用")
            apply_btn.setFixedWidth(50)
            apply_btn.setStyleSheet(BUTTON_STYLE)
            apply_btn.clicked.connect(
                lambda checked, idx=idx, e=entry: self._apply_hex(idx, e.text())
            )
            self.color_grid.addWidget(apply_btn, row, 3)

    def _pick_color(self, idx: int) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            name = self._current_scheme_name()
            p.set_palette_scheme_color(self.app, name, idx, color.name())
            self._render_colors(name)

    def _apply_hex(self, idx: int, text: str) -> None:
        normalized = p.normalize_color_value(text)
        if normalized:
            name = self._current_scheme_name()
            p.set_palette_scheme_color(self.app, name, idx, normalized)
            self._render_colors(name)

    def _current_scheme_name(self) -> str:
        item = self.scheme_list.currentItem()
        return item.text() if item else "默认方案"

    def _add_scheme(self) -> None:
        name = self.entry_new.text().strip() or "新方案"
        schemes = self.app._app_state.setdefault("palette_schemes", {})
        if name in schemes:
            QMessageBox.warning(self, "提示", f'调色板方案"{name}"已存在')
            return
        schemes[name] = {}
        p.set_palette_scheme_slot_count(self.app, name, 8)
        p.materialize_palette_scheme(self.app, name)
        self.entry_new.clear()
        self._populate_scheme_list()

    def _delete_scheme(self) -> None:
        name = self._current_scheme_name()
        schemes = self.app._app_state.get("palette_schemes", {})
        if len(schemes) <= 1:
            QMessageBox.warning(self, "提示", "至少保留一套调色板方案")
            return
        confirm = QMessageBox.question(
            self, "确认", f'确定删除"{name}"吗？',
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        schemes.pop(name, None)
        self._populate_scheme_list()

    def _add_color_slot(self) -> None:
        name = self._current_scheme_name()
        count = p.palette_scheme_slot_count(self.app, name)
        p.set_palette_scheme_slot_count(self.app, name, count + 1)
        p.materialize_palette_scheme(self.app, name)
        self._render_colors(name)

    def _apply_to_current(self) -> None:
        p.apply_palette_scheme_to_current(self.app)
        self.schemes_updated.emit()

    def _apply_to_comparison(self) -> None:
        p.apply_palette_scheme_to_comparison(self.app)
        self.schemes_updated.emit()
