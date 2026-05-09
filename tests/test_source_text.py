from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = (
    "榛樿",
    "绗瑊",
    "鎷",
    "閿",
    "R虏",
    "脳",
    "鉁",
)


class SourceTextTests(unittest.TestCase):
    def test_python_source_does_not_contain_common_mojibake_markers(self) -> None:
        offenders: list[str] = []
        for path in (ROOT / "src").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in MOJIBAKE_MARKERS):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
