"""UI 组件工厂函数与辅助函数。"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit("缺少依赖 customtkinter") from exc

from gui.theme import (
    ACCENT,
    BORDER_COLOR,
    COMBO_BUTTON_COLOR,
    COMBO_BUTTON_HOVER,
    COMBO_DROPDOWN_BG,
    COMBO_DROPDOWN_HOVER,
    ENTRY_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def make_section_label(parent: ctk.CTkFrame, text: str, row: int) -> ctk.CTkLabel:
    label = ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=ACCENT,
        anchor="w",
    )
    label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(14, 4))
    return label


def make_entry_row(
    parent: ctk.CTkFrame,
    label: str,
    row: int,
    *,
    default: str = "",
    placeholder: str = "",
    width: int = 220,
) -> ctk.CTkEntry:
    ctk.CTkLabel(parent, text=label, text_color=TEXT_SECONDARY, anchor="e").grid(
        row=row, column=0, sticky="e", padx=(10, 4), pady=4
    )
    entry = ctk.CTkEntry(
        parent,
        width=width,
        placeholder_text=placeholder,
        border_color=BORDER_COLOR,
        fg_color=ENTRY_BG,
        text_color=TEXT_PRIMARY,
    )
    entry.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
    if default:
        entry.insert(0, default)
    return entry


def make_combo_row(
    parent: ctk.CTkFrame,
    label: str,
    row: int,
    *,
    values: list[str],
    width: int = 220,
    command=None,
) -> ctk.CTkComboBox:
    ctk.CTkLabel(parent, text=label, text_color=TEXT_SECONDARY, anchor="e").grid(
        row=row, column=0, sticky="e", padx=(10, 4), pady=4
    )
    combo = ctk.CTkComboBox(
        parent,
        values=values or [""],
        width=width,
        command=command,
        border_color=BORDER_COLOR,
        fg_color=ENTRY_BG,
        button_color=COMBO_BUTTON_COLOR,
        button_hover_color=COMBO_BUTTON_HOVER,
        dropdown_fg_color=COMBO_DROPDOWN_BG,
        dropdown_hover_color=COMBO_DROPDOWN_HOVER,
        dropdown_text_color=TEXT_PRIMARY,
        text_color=TEXT_PRIMARY,
    )
    combo.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
    combo.set((values or [""])[0])
    return combo


def set_combo_values(combo: ctk.CTkComboBox, values: list[str], preferred: str | None = None) -> None:
    items = values or [""]
    combo.configure(values=items)
    combo.set(preferred if preferred in items else items[0])


def set_option_values(option_menu, values: list[str], preferred: str | None = None) -> None:
    items = values or [""]
    option_menu.configure(values=items)
    option_menu.set(preferred if preferred in items else items[0])


def set_entry_text(entry: ctk.CTkEntry, text: str) -> None:
    entry.delete(0, "end")
    entry.insert(0, text)


def path_labels(paths: list[Path]) -> dict[str, Path]:
    labels: dict[str, Path] = {}
    name_counts: dict[str, int] = {}
    for path in paths:
        name_counts[path.name] = name_counts.get(path.name, 0) + 1
    for path in paths:
        label = path.name if name_counts[path.name] == 1 else f"{path.name} | {path.parent}"
        labels[label] = path
    return labels


def output_stem(tdms_path: Path, segment_index: int, segment_count: int) -> str:
    if segment_count <= 1:
        return tdms_path.stem
    return f"{tdms_path.stem}_seg{segment_index + 1}"


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


def resolved_output_stem(tdms_path: Path, export_name: str) -> str:
    return export_name.strip() or tdms_path.stem


def priority_label_to_key(label: str) -> str:
    return "slope" if label.strip() == "斜率更低优先" else "r2"


def priority_key_to_label(key: str) -> str:
    return "斜率更低优先" if key == "slope" else "R²优先"


def parse_segment_selection(text: str, segment_count: int, active_index: int) -> list[int]:
    raw = text.strip()
    if not raw:
        result: list[int] = []
    elif raw.lower() == "all":
        result = list(range(segment_count))
    else:
        unique: set[int] = set()
        for chunk in raw.replace("，", ",").split(","):
            part = chunk.strip()
            if not part:
                continue
            if "-" in part:
                left_text, right_text = part.split("-", 1)
                left = int(left_text)
                right = int(right_text)
                start, end = sorted((left, right))
                for item in range(start, end + 1):
                    unique.add(item - 1)
            else:
                unique.add(int(part) - 1)
        result = sorted(unique)
    for index in result:
        if index < 0 or index >= segment_count:
            raise ValueError(f"分段选择超出范围，当前共 {segment_count} 段")
    return result


def segment_selection_text(indices: list[int]) -> str:
    return ",".join(str(index + 1) for index in indices)
