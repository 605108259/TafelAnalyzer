from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication


def _qapp():
    return QApplication.instance() or QApplication([])


class PanelIncrementalUpdateTests(unittest.TestCase):
    def test_file_processed_update_reuses_existing_row_widget(self) -> None:
        _qapp()
        from ui.panels.file_segment import FileSegmentPanel

        panel = FileSegmentPanel()
        paths = [Path(f"D:/data/file_{index}.cor") for index in range(8)]
        panel.set_file_paths(paths, set())
        original = panel.file_list.itemWidget(panel.file_list.item(3))

        panel.set_processed(paths[3])

        self.assertEqual(panel.file_list.count(), len(paths))
        self.assertIs(panel.file_list.itemWidget(panel.file_list.item(3)), original)

    def test_file_metadata_refresh_reuses_existing_row_widget(self) -> None:
        _qapp()
        from ui.panels.file_segment import FileSegmentPanel

        panel = FileSegmentPanel()
        paths = [Path(f"D:/data/file_{index}.cor") for index in range(4)]
        panel.set_file_paths(paths, set())
        original = panel.file_list.itemWidget(panel.file_list.item(2))

        panel.set_file_paths(paths, {str(paths[2])}, names={str(paths[2]): "renamed"})

        self.assertIs(panel.file_list.itemWidget(panel.file_list.item(2)), original)

    def test_file_path_append_reuses_existing_rows(self) -> None:
        _qapp()
        from ui.panels.file_segment import FileSegmentPanel

        panel = FileSegmentPanel()
        paths = [Path(f"D:/data/file_{index}.cor") for index in range(3)]
        panel.set_file_paths(paths, set())
        original = panel.file_list.itemWidget(panel.file_list.item(1))

        panel.set_file_paths(paths + [Path("D:/data/new_file.cor")], set())

        self.assertEqual(panel.file_list.count(), 4)
        self.assertIs(panel.file_list.itemWidget(panel.file_list.item(1)), original)

    def test_file_path_remove_reuses_remaining_rows(self) -> None:
        _qapp()
        from ui.panels.file_segment import FileSegmentPanel

        panel = FileSegmentPanel()
        paths = [Path(f"D:/data/file_{index}.cor") for index in range(4)]
        panel.set_file_paths(paths, set())
        survivor = panel.file_list.itemWidget(panel.file_list.item(2))

        panel.set_file_paths([paths[0], paths[2], paths[3]], set())

        self.assertEqual(panel.file_list.count(), 3)
        self.assertIs(panel.file_list.itemWidget(panel.file_list.item(1)), survivor)

    def test_comparison_set_items_reuses_rows_when_ids_are_unchanged(self) -> None:
        _qapp()
        from ui.panels.comparison import ComparisonPanel

        panel = ComparisonPanel()
        items = self._comparison_items(5)
        panel.set_items(items)
        original = panel.item_list.itemWidget(panel.item_list.item(1))

        updated = [dict(item, edit_name=f"updated {index}") for index, item in enumerate(items)]
        panel.set_items(updated)

        self.assertIs(panel.item_list.itemWidget(panel.item_list.item(1)), original)

    def test_comparison_reorder_reuses_stable_row_widgets_and_updates_ids(self) -> None:
        _qapp()
        from ui.panels.comparison import ComparisonPanel

        panel = ComparisonPanel()
        items = self._comparison_items(3)
        panel.set_items(items)
        first_row_widget = panel.item_list.itemWidget(panel.item_list.item(0))
        second_row_widget = panel.item_list.itemWidget(panel.item_list.item(1))

        panel.set_items([items[1], items[0], items[2]])

        self.assertEqual(panel.item_id_at(0), "item-1")
        self.assertEqual(panel.item_id_at(1), "item-0")
        self.assertIs(panel.item_list.itemWidget(panel.item_list.item(0)), first_row_widget)
        self.assertIs(panel.item_list.itemWidget(panel.item_list.item(1)), second_row_widget)

    def _comparison_items(self, count: int) -> list[dict]:
        return [
            {
                "item_id": f"item-{index}",
                "display_name": f"item {index}",
                "edit_name": f"item {index}",
                "segment_label": "",
                "color": "#2563eb",
                "visible": True,
                "file_name": f"file_{index}.cor",
                "segment_index": index,
            }
            for index in range(count)
        ]


if __name__ == "__main__":
    unittest.main()
