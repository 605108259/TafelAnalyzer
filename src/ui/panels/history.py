from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal, QSize, Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ui.theme import (
    ACCENT,
    ACCENT_BUTTON_STYLE,
    BG_CARD,
    BG_HOVER,
    BORDER,
    BUTTON_STYLE,
    DANGER_BUTTON_STYLE,
    PANEL_STYLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class HistoryEntryWidget(QWidget):
    def __init__(self, entry: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("HistoryEntry")
        self._entry = entry
        self._highlighted = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = str(entry.get("title") or "未命名项目")
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
        layout.addWidget(self.title_label)

        files = [str(path) for path in entry.get("files", []) if str(path).strip()]
        first_file = Path(files[0]).name if files else "无数据文件"
        if len(files) > 1:
            first_file = f"{first_file} +{len(files) - 1}"
        self.file_label = QLabel(first_file)
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.file_label)

        updated_at = str(entry.get("updated_at") or "未保存时间")
        self.time_label = QLabel(f"最后编辑：{updated_at}")
        self.time_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        layout.addWidget(self.time_label)

        self.set_highlighted(False)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), 72))
        return hint

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlighted = highlighted
        if highlighted:
            self.setStyleSheet(
                "QWidget#HistoryEntry { "
                "background: #dbeafe; "
                f"border: 1px solid {ACCENT}; "
                f"border-left: 4px solid {ACCENT}; "
                "border-radius: 7px; "
                "}"
            )
            self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 800;")
            self.file_label.setStyleSheet("color: #1e40af; font-size: 11px; font-weight: 600;")
            self.time_label.setStyleSheet("color: #1d4ed8; font-size: 10px;")
        else:
            self.setStyleSheet(
                "QWidget#HistoryEntry { "
                f"background: {BG_CARD}; "
                f"border: 1px solid {BORDER}; "
                "border-radius: 7px; "
                "}"
                "QWidget#HistoryEntry:hover { "
                f"background: {BG_HOVER}; "
                "}"
            )
            self.title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
            self.file_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            self.time_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")


class HistoryPanel(QWidget):
    restore_requested = Signal(str)
    remove_requested = Signal(str)
    clear_requested = Signal()
    selected_entry_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)
        self._entries: list[dict[str, Any]] = []
        self._entry_by_id: dict[str, dict[str, Any]] = {}
        self._entries_signature: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("历史项目")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        hint = QLabel("自动保存的项目缓存。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(hint)

        self.history_list = QListWidget()
        self.history_list.setSpacing(8)
        self.history_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.history_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { background: transparent; padding: 0px; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        self.history_list.currentItemChanged.connect(self._on_current_changed)
        self.history_list.itemDoubleClicked.connect(self._restore_item)
        layout.addWidget(self.history_list, stretch=1)

        row = QHBoxLayout()
        btn_restore = QPushButton("恢复")
        btn_restore.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.clicked.connect(self.restore_current)
        row.addWidget(btn_restore)

        btn_remove = QPushButton("删除")
        btn_remove.setStyleSheet(BUTTON_STYLE)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.clicked.connect(self.remove_current)
        row.addWidget(btn_remove)
        layout.addLayout(row)

        btn_clear = QPushButton("清空历史")
        btn_clear.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_requested.emit)
        layout.addWidget(btn_clear)

    def set_entries(self, entries: list[dict[str, Any]]) -> bool:
        current_id = self.current_entry_id()
        next_entries = list(entries)
        next_signature = self._signature(next_entries)
        if next_signature == self._entries_signature:
            self._entries = next_entries
            self._entry_by_id = self._build_entry_map(next_entries)
            return False

        self._entries = next_entries
        self._entries_signature = next_signature
        self._entry_by_id = self._build_entry_map(self._entries)
        self._clear_items()
        self.history_list.clear()
        for entry in self._entries:
            entry_id = str(entry.get("id") or entry.get("cache_path") or "")
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry_id)
            item.setToolTip(str(entry.get("cache_path") or ""))
            widget = HistoryEntryWidget(entry)
            item.setSizeHint(widget.sizeHint())
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, widget)

        if not self._entries:
            self.selected_entry_changed.emit(None)
            return True

        target_row = 0
        if current_id:
            for row in range(self.history_list.count()):
                item = self.history_list.item(row)
                if str(item.data(Qt.ItemDataRole.UserRole)) == current_id:
                    target_row = row
                    break
        self.history_list.setCurrentRow(target_row)
        self._highlight_current()
        self.selected_entry_changed.emit(self.current_entry())
        return True

    def current_entry_id(self) -> str:
        item = self.history_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def current_entry(self) -> dict[str, Any] | None:
        entry_id = self.current_entry_id()
        if not entry_id:
            return None
        return self._entry_by_id.get(entry_id)

    def restore_current(self) -> None:
        item = self.history_list.currentItem()
        if item is not None:
            self._restore_item(item)

    def remove_current(self) -> None:
        entry_id = self.current_entry_id()
        if entry_id:
            self.remove_requested.emit(entry_id)

    def _restore_item(self, item: QListWidgetItem) -> None:
        entry_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        entry = self._entry_by_id.get(entry_id)
        if entry is not None:
            self.restore_requested.emit(str(entry.get("cache_path") or ""))

    def _on_current_changed(self, _current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._highlight_current()
        self.selected_entry_changed.emit(self.current_entry())

    def _highlight_current(self) -> None:
        current = self.history_list.currentItem()
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            widget = self.history_list.itemWidget(item)
            if isinstance(widget, HistoryEntryWidget):
                widget.set_highlighted(item is current)

    def _clear_items(self) -> None:
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            widget = self.history_list.itemWidget(item)
            if widget is None:
                continue
            self.history_list.removeItemWidget(item)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()

    def _signature(self, entries: list[dict[str, Any]]) -> tuple[tuple[str, str, str, str, tuple[str, ...]], ...]:
        return tuple(
            (
                str(entry.get("id") or entry.get("cache_path") or ""),
                str(entry.get("title") or ""),
                str(entry.get("updated_at") or ""),
                str(entry.get("cache_path") or ""),
                tuple(str(path) for path in entry.get("files", []) if str(path).strip()),
            )
            for entry in entries
        )

    def _build_entry_map(self, entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            str(entry.get("id") or entry.get("cache_path") or ""): entry
            for entry in entries
            if str(entry.get("id") or entry.get("cache_path") or "")
        }
