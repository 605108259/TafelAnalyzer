from __future__ import annotations

import re

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex_color(value: str, fallback: str = "#2563eb") -> str:
    color = (value or "").strip()
    if color and not color.startswith("#"):
        color = f"#{color}"
    return color.lower() if HEX_COLOR_RE.match(color) else fallback


def is_hex_color(value: str) -> bool:
    color = (value or "").strip()
    if color and not color.startswith("#"):
        color = f"#{color}"
    return bool(HEX_COLOR_RE.match(color))


def is_light_color(hex_color: str) -> bool:
    color = normalize_hex_color(hex_color).lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance > 150


def readable_text_color(hex_color: str) -> str:
    return "#0f172a" if is_light_color(hex_color) else "#ffffff"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """将 hex 颜色转为 (R, G, B) 元组。"""
    text = normalize_hex_color(color)
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """将 (R, G, B) 元组转为 hex 颜色。"""
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(v))) for v in rgb))


def interpolate_hex(left: str, right: str, t: float) -> str:
    """在两个 hex 颜色间线性插值。"""
    a = hex_to_rgb(left)
    b = hex_to_rgb(right)
    r = round(a[0] + (b[0] - a[0]) * t)
    g = round(a[1] + (b[1] - a[1]) * t)
    blue = round(a[2] + (b[2] - a[2]) * t)
    return rgb_to_hex((r, g, blue))



