import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ui.color_utils import hex_to_rgb, rgb_to_hex, interpolate_hex, normalize_hex_color


def test_hex_to_rgb():
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)


def test_rgb_to_hex():
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"


def test_interpolate_hex():
    assert interpolate_hex("#000000", "#ffffff", 0.5) == "#808080"


def test_normalize_hex_color():
    assert normalize_hex_color("ff0000") == "#ff0000"
    assert normalize_hex_color("#GG0000") == "#2563eb"
