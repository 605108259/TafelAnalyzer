"""工具函数：channel 解析、字体管理、范围规范化、段选择解析。"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
from matplotlib import font_manager


def _channel_basename(name: str) -> str:
    return name.split("/")[-1]


def resolve_channel_name(channels: dict[str, np.ndarray], name: str) -> str:
    if name in channels:
        return name
    matches = [key for key in channels if _channel_basename(key) == name]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"未找到 channel：{name}，可用 channel={list(channels)}")
    raise ValueError(f"channel 名称不唯一：{name}，请使用完整名称，可用 channel={matches}")


def pick_channel_name(
    channels: dict[str, np.ndarray],
    preferred: Iterable[str],
    user_input: str | None = None,
) -> str:
    if user_input:
        return resolve_channel_name(channels, user_input)
    for target in preferred:
        for key in channels:
            if key == target or _channel_basename(key) == target:
                return key
    raise ValueError(f"未找到匹配 channel：{list(preferred)}，可用 channel={list(channels)}")


@lru_cache(maxsize=1)
def get_cjk_font_name() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "Microsoft JhengHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
    ]
    for name in preferred:
        if name in available:
            return name
    return "DejaVu Sans"


def apply_matplotlib_cjk(matplotlib_module) -> str:
    font_name = get_cjk_font_name()
    matplotlib_module.rcParams["font.family"] = [font_name]
    matplotlib_module.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
    matplotlib_module.rcParams["axes.unicode_minus"] = False
    return font_name


# ── Range text parsing ───────────────────────────────────────────────


RANGE_TEXT_PATTERN = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*-\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$"
)


def parse_range_text(
    text: str,
    label: str,
    *,
    integer: bool = False,
    minimum: float | None = None,
    allow_empty: bool = False,
) -> tuple[float, float] | tuple[int, int] | None:
    raw = text.strip()
    if not raw:
        if allow_empty:
            return None
        raise ValueError(f"{label}不能为空")
    match = RANGE_TEXT_PATTERN.fullmatch(raw)
    if match is None:
        raise ValueError(f'{label}格式应为"起点-终点"')
    low = float(match.group(1))
    high = float(match.group(2))
    if low > high:
        low, high = high, low
    if minimum is not None and (low < minimum or high < minimum):
        raise ValueError(f"{label}不能小于 {minimum}")
    if integer:
        if not low.is_integer() or not high.is_integer():
            raise ValueError(f"{label}必须是整数范围")
        return int(low), int(high)
    return float(low), float(high)


# ── Fit priority helpers ─────────────────────────────────────────────


def priority_label_to_key(label: str) -> str:
    return "slope" if label.strip() == "斜率更低优先" else "r2"


