from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt


class SummaryTable(QTableWidget):
    """Comparison results summary table with sorting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["别名", "段", "斜率 (mV/dec)", "R²", "点数"])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)

    def set_items(self, items_data: list[dict]) -> None:
        """items_data: [{alias, segment, slope, r2, n_points}]"""
        self.setSortingEnabled(False)
        self.setRowCount(len(items_data))
        for row, data in enumerate(items_data):
            self.setItem(row, 0, QTableWidgetItem(data.get("alias", "")))
            self.setItem(row, 1, QTableWidgetItem(str(data.get("segment", ""))))
            slope = data.get("slope")
            self.setItem(row, 2, QTableWidgetItem(
                f"{slope:.1f}" if slope is not None else ""
            ))
            r2 = data.get("r2")
            self.setItem(row, 3, QTableWidgetItem(
                f"{r2:.4f}" if r2 is not None else ""
            ))
            self.setItem(row, 4, QTableWidgetItem(str(data.get("n_points", ""))))
        self.setSortingEnabled(True)
