from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QColorDialog,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, BG_HOVER, BG_SELECTED, TEXT_PRIMARY,
    TEXT_SECONDARY, SUCCESS, TEXT_DISABLED, ACCENT, ACCENT_HOVER, ACCENT_BUTTON_STYLE,
)


class SegmentItemWidget(QWidget):
    """One row in the segment list: color bar + radio + label + R2."""

    activated = Signal(int)  # segment index
    color_clicked = Signal(int)  # segment index

    def __init__(self, index: int, label: str, color: str,
                 is_active: bool, r2: float | None):
        super().__init__()
        self.segment_index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Color strip
        self.color_bar = QPushButton()
        self.color_bar.setFixedSize(8, 32)
        self.color_bar.setStyleSheet(
            f"QPushButton {{ background: {color}; border: none; border-radius: 2px; }}"
            f"QPushButton:hover {{ border: 1px solid {ACCENT}; }}"
        )
        self.color_bar.setCursor(Qt.PointingHandCursor)
        self.color_bar.clicked.connect(lambda: self.color_clicked.emit(index))
        layout.addWidget(self.color_bar)

        # Radio indicator (circle or empty circle)
        self.radio = QLabel(chr(0x25C9) if is_active else chr(0x25CB))
        self.radio.setStyleSheet(
            f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 14px;"
        )
        layout.addWidget(self.radio)

        # Segment label
        self.name_label = QLabel(label)
        self.name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)

        # R2 badge
        if r2 is not None:
            r2_label = QLabel(f"R2={r2:.4f}")
            r2_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
            layout.addWidget(r2_label)
        else:
            na_label = QLabel(chr(0x672A) + chr(0x62DF) + chr(0x5408))
            na_label.setStyleSheet(f"color: {TEXT_DISABLED}; font-size: 11px;")
            layout.addWidget(na_label)


class SegmentPanel(QWidget):
    """Side panel for segment selection and management."""

    segment_activated = Signal(int)
    segment_color_changed = Signal(int, str)  # index, hex_color
    add_to_comparison = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel(chr(0x1F4CB) + " " + chr(0x5206) + chr(0x6BB5) + chr(0x7BA1) + chr(0x7406))
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Select all / clear all
        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton(chr(0x5168) + chr(0x9009))
        self.btn_select_all.setStyleSheet(BUTTON_STYLE)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_select_all)

        self.btn_clear_all = QPushButton(chr(0x5168) + chr(0x4E0D) + chr(0x9009))
        self.btn_clear_all.setStyleSheet(BUTTON_STYLE)
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_clear_all)
        layout.addLayout(btn_row)

        # Segment list
        self.segment_list = QListWidget()
        self.segment_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        self.segment_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.segment_list, stretch=1)

        # Add to comparison
        self.btn_add_compare = QPushButton(chr(0x1F4CC) + " " + chr(0x6DFB) + chr(0x52A0) + chr(0x5230) + chr(0x5BF9) + chr(0x6BD4))
        self.btn_add_compare.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_add_compare.setCursor(Qt.PointingHandCursor)
        self.btn_add_compare.clicked.connect(self.add_to_comparison.emit)
        layout.addWidget(self.btn_add_compare)

        self._segments: list[dict] = []
        self._active_index: int = 0

    def set_segments(self, segments: list[dict], active_index: int,
                     colors: dict[int, str], fit_by_segment: dict) -> None:
        self._segments = segments
        self._active_index = active_index
        self._rebuild(colors, fit_by_segment)

    def _rebuild(self, colors: dict[int, str], fit_by_segment: dict) -> None:
        self.segment_list.clear()
        for seg in self._segments:
            idx = seg["index"]
            color = colors.get(idx, "#94a3b8")
            is_active = (idx == self._active_index)
            fit = fit_by_segment.get(idx)
            r2 = fit.r2 if fit is not None else None

            item = QListWidgetItem()
            widget = SegmentItemWidget(idx, seg["label"], color, is_active, r2)
            widget.activated.connect(self._on_activate)
            widget.color_clicked.connect(self._on_color_click)
            item.setSizeHint(widget.sizeHint())
            self.segment_list.addItem(item)
            self.segment_list.setItemWidget(item, widget)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.segment_list.itemWidget(item)
        if isinstance(widget, SegmentItemWidget):
            self._on_activate(widget.segment_index)

    def _on_activate(self, index: int) -> None:
        self._active_index = index
        self.segment_activated.emit(index)
        # Refresh radio indicators
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            w = self.segment_list.itemWidget(item)
            if isinstance(w, SegmentItemWidget):
                is_active = (w.segment_index == index)
                w.radio.setText(chr(0x25C9) if is_active else chr(0x25CB))
                w.radio.setStyleSheet(
                    f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 14px;"
                )

    def _on_color_click(self, index: int) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.segment_color_changed.emit(index, color.name())
