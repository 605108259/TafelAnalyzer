from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


from core.version import UpdateInfo, is_newer_version, parse_version
from ui.updater import _download_target_path


def test_parse_version_splits_numeric_parts():
    assert parse_version("1.2.10") > parse_version("1.2.3")


def test_is_newer_version():
    assert is_newer_version("1.0.2", "1.0.1")
    assert not is_newer_version("1.0.1", "1.0.1")
    assert not is_newer_version("1.0.0", "1.0.1")


def test_download_target_path_sanitizes_manifest_filename():
    info = UpdateInfo(
        version="1.2.3",
        url="http://example.invalid/download/TAFSQ-1.2.3-setup.exe",
        filename='TAFSQ:1.2.3"*setup.exe',
    )
    path = _download_target_path(info)
    assert path.name == "TAFSQ1.2.3setup.exe"
