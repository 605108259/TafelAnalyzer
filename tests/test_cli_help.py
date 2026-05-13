from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_help_prints_without_encoding_error() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "run_cli.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "UnicodeEncodeError" not in result.stderr
