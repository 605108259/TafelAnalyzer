from __future__ import annotations

import json
import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication

from ui.central.history_workspace import HistoryWorkspace


def test_history_workspace_reads_v3_directory_preview(tmp_path):
    app = QApplication.instance() or QApplication([])
    cache_dir = tmp_path / "2026-05-10 17-24-04"
    cache_dir.mkdir()
    (cache_dir / "manifest.json").write_text(
        json.dumps(
            {
                "cache_format_version": 3,
                "selected_paths": ["D:/data/a.cor"],
                "current_path": "D:/data/a.cor",
                "chart_view_state": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (cache_dir / "file_ui.json").write_text(
        json.dumps({"D:/data/a.cor": {"potential_formula": "[V]"}}),
        encoding="utf-8",
    )
    (cache_dir / "comparison.json").write_text(
        json.dumps({"items": [{"file_name": "a", "segment_index": 0}]}),
        encoding="utf-8",
    )

    widget = HistoryWorkspace()
    payload, error = widget._load_payload(str(cache_dir))

    assert error == ""
    assert payload["cache_format_version"] == 3
    assert payload["selected_paths"] == ["D:/data/a.cor"]
    assert payload["file_ui_cache"]["D:/data/a.cor"]["potential_formula"] == "[V]"
