from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.types import COMPARISON_COLORS, ComparisonItem
from core import comparison as comp
from ui.color_utils import normalize_hex_color


DEFAULT_SCHEME_NAME = "默认方案"
LEGACY_DEFAULT_SCHEME_NAMES = {"\u699b\u6a3f\ue17b\u93c2\u89c4\ue50d", "默认配色", "Default"}


def normalize_palette_scheme_name(name: str | None) -> str:
    text = str(name or "").strip()
    return DEFAULT_SCHEME_NAME if not text or text in LEGACY_DEFAULT_SCHEME_NAMES else text


@dataclass(frozen=True)
class QColorCompat:
    value: str

    @property
    def r(self) -> int:
        return int(normalize_hex_color(self.value)[1:3], 16)

    @property
    def g(self) -> int:
        return int(normalize_hex_color(self.value)[3:5], 16)

    @property
    def b(self) -> int:
        return int(normalize_hex_color(self.value)[5:7], 16)


def create_initial_state() -> dict[str, Any]:
    return {
        "selected_paths": [],
        "tdms_path": None,
        "channels": None,
        "segments": [],
        "segment_colors": {},
        "active_segment_index": 0,
        "selected_segment_indices": [],
        "prepared": None,
        "fit": None,
        "fit_by_segment": {},
        "prepared_by_segment": {},
        "fit_error_by_segment": {},
        "manual_mode": False,
        "manual_file_path": None,
        "manual_generation": None,
        "interaction_mode": "idle",
        "selector": None,
        "active_chart_mode": None,
        "comparison_mode": False,
        "comparison_items": [],
        "comparison_highlight_row": -1,
        "palette_schemes": {
            DEFAULT_SCHEME_NAME: {str(i): color for i, color in enumerate(COMPARISON_COLORS)}
        },
        "palette_scheme_slot_counts": {DEFAULT_SCHEME_NAME: len(COMPARISON_COLORS)},
        "active_palette_scheme": DEFAULT_SCHEME_NAME,
        "saved_parameter_defaults": {},
        "file_ui_cache": {},
        "result_cache": {},
        "current_result_keys": {},
        "_op_generation": 0,
        "_fitting_lock": False,
    }


_RESULT_RESET_DEFAULTS: dict[str, Any] = {
    "channels": None,
    "segments": [],
    "segment_colors": {},
    "prepared": None,
    "fit": None,
    "prepared_by_segment": {},
    "fit_by_segment": {},
    "fit_error_by_segment": {},
    "selected_segment_indices": [],
    "active_segment_index": 0,
    "single_plot_view_state": None,
    "single_plot_default_view_state": None,
    "ax_tafel": None,
    "manual_mode": False,
    "manual_file_path": None,
    "manual_generation": None,
    "interaction_mode": "idle",
    "selector": None,
}


def _reset_result_fields(raw: dict[str, Any]) -> None:
    raw.update(_RESULT_RESET_DEFAULTS)


@dataclass
class FileState:
    raw: dict[str, Any]

    @property
    def selected_paths(self) -> list[Path]:
        return self.raw.setdefault("selected_paths", [])

    @property
    def current_path(self) -> Path | None:
        return self.raw.get("tdms_path")

    def set_current_path(self, path: Path | None) -> None:
        self.raw["tdms_path"] = path

    def display_name(self, path: Path) -> str:
        return (
            self.raw.setdefault("file_ui_cache", {}).get(str(path), {}).get("file_alias")
            or path.stem
        )

    def display_names(self, paths: list[Path] | None = None) -> dict[str, str]:
        paths = self.selected_paths if paths is None else paths
        return {str(path): self.display_name(path) for path in paths}

    def set_alias(self, path: Path, alias: str) -> None:
        entry = self.raw.setdefault("file_ui_cache", {}).setdefault(str(path), {})
        entry["file_alias"] = alias.strip() or path.stem

    def merge_paths(self, paths: list[Path]) -> list[Path]:
        existing = list(self.selected_paths)
        new_paths = [path for path in paths if path not in existing]
        self.raw["selected_paths"] = existing + new_paths
        return new_paths

    def remove_path(self, path: Path) -> list[Path]:
        self.raw.setdefault("file_ui_cache", {}).pop(str(path), None)
        self.raw.setdefault("current_result_keys", {}).pop(str(path), None)
        if path in self.selected_paths:
            self.selected_paths.remove(path)
        return list(self.selected_paths)

    def reset_current_result(self) -> None:
        _reset_result_fields(self.raw)

    def clear_current_file(self) -> None:
        self.raw["tdms_path"] = None
        self.reset_current_result()


@dataclass
class AnalysisState:
    raw: dict[str, Any]

    @property
    def channels(self) -> dict[str, Any] | None:
        return self.raw.get("channels")

    @property
    def segments(self) -> list[Any]:
        return self.raw.get("segments", [])

    @property
    def prepared_by_segment(self) -> dict[int, Any]:
        return self.raw.get("prepared_by_segment", {})

    @property
    def fit_by_segment(self) -> dict[int, Any]:
        return self.raw.get("fit_by_segment", {})

    @property
    def fit_error_by_segment(self) -> dict[int, str]:
        return self.raw.get("fit_error_by_segment", {})

    @property
    def prepared(self) -> Any:
        return self.raw.get("prepared")

    @property
    def fit(self) -> Any:
        return self.raw.get("fit")

    def begin_file_load(self, path: Path) -> None:
        self.raw["tdms_path"] = path
        _reset_result_fields(self.raw)

    def apply_loaded_file(
        self,
        *,
        channels: Any,
        segment_infos: list[Any],
        segment_colors: dict[int, str],
    ) -> list[dict[str, Any]]:
        segment_rows = [
            {"index": segment.index, "label": segment.label}
            for segment in segment_infos
        ]
        self.raw["channels"] = channels
        self.raw["segments"] = segment_rows
        self.raw["segment_colors"] = dict(segment_colors)
        self.raw["prepared"] = None
        self.raw["fit"] = None
        self.raw["prepared_by_segment"] = {}
        self.raw["fit_by_segment"] = {}
        self.raw["fit_error_by_segment"] = {}
        self.raw["active_segment_index"] = 0
        self.raw["selected_segment_indices"] = [segment.index for segment in segment_infos]
        return segment_rows

    def merge_fit_results(
        self,
        *,
        prepared_map: dict[int, Any],
        fit_map: dict[int, Any],
        error_map: dict[int, str],
    ) -> Any | None:
        previous_prepared = dict(self.raw.get("prepared_by_segment", {}))
        previous_prepared.update(prepared_map)
        self.raw["prepared_by_segment"] = previous_prepared

        previous_fit = dict(self.raw.get("fit_by_segment", {}))
        previous_fit.update(fit_map)
        self.raw["fit_by_segment"] = previous_fit

        previous_errors = dict(self.raw.get("fit_error_by_segment", {}))
        previous_errors.update(error_map)
        self.raw["fit_error_by_segment"] = previous_errors

        active_index = int(self.raw.get("active_segment_index", 0))
        active_prepared = prepared_map.get(active_index)
        if active_prepared is None and prepared_map:
            active_prepared = next(iter(prepared_map.values()))
        self.raw["prepared"] = active_prepared
        self.raw["fit"] = fit_map.get(
            active_prepared.segment.index if active_prepared else active_index
        )
        return active_prepared

    def apply_manual_fit(self, *, segment_index: int, fit: Any) -> None:
        self.raw.setdefault("fit_by_segment", {})[int(segment_index)] = fit
        self.raw.setdefault("fit_error_by_segment", {}).pop(int(segment_index), None)
        self.raw["fit"] = fit


@dataclass
class SegmentState:
    raw: dict[str, Any]

    @property
    def selected_indices(self) -> list[int]:
        return list(self.raw.get("selected_segment_indices", []))

    @property
    def active_index(self) -> int:
        return int(self.raw.get("active_segment_index", 0))

    def set_active(self, index: int) -> None:
        index = int(index)
        self.raw["active_segment_index"] = index
        if index < 0:
            return
        prepared = self.raw.get("prepared_by_segment", {}).get(index)
        if prepared is not None:
            self.raw["prepared"] = prepared
            self.raw["fit"] = self.raw.get("fit_by_segment", {}).get(index)

    def set_selected(self, indices: list[int]) -> None:
        self.raw["selected_segment_indices"] = sorted({int(index) for index in indices})

    def toggle(self, index: int, checked: bool) -> None:
        selected = set(self.selected_indices)
        if checked:
            selected.add(int(index))
        else:
            selected.discard(int(index))
        self.set_selected(list(selected))

    def select_all_loaded(self) -> None:
        self.set_selected([seg["index"] for seg in self.raw.get("segments", [])])

    def clear_selection(self) -> None:
        self.raw["selected_segment_indices"] = []


@dataclass
class ComparisonState:
    raw: dict[str, Any]

    @property
    def items(self) -> list[ComparisonItem]:
        return self.raw.setdefault("comparison_items", [])

    @property
    def highlight_row(self) -> int:
        return int(self.raw.get("comparison_highlight_row", -1))

    def set_highlight(self, row: int) -> None:
        if not self.items:
            self.raw["comparison_highlight_row"] = -1
            return
        self.raw["comparison_highlight_row"] = row if 0 <= row < len(self.items) else -1

    def item_data(self) -> list[dict[str, Any]]:
        return [
            {
                "item_id": item.item_id,
                "display_name": comp.comparison_item_label(item),
                "edit_name": comp.comparison_item_label(item),
                "segment_label": "",
                "color": item.color,
                "visible": item.visible,
            }
            for item in self.items
        ]

    def item_by_id(self, item_id: str) -> ComparisonItem | None:
        return next((item for item in self.items if item.item_id == item_id), None)

    def has_item(self, item_id: str) -> bool:
        return self.item_by_id(item_id) is not None

    def add(self, item: ComparisonItem) -> bool:
        if self.has_item(item.item_id):
            return False
        self.items.append(item)
        return True

    def remove(self, item_id: str) -> None:
        removed_index = next((i for i, item in enumerate(self.items) if item.item_id == item_id), -1)
        if removed_index < 0:
            return
        current = self.highlight_row
        self.raw["comparison_items"] = [
            item for item in self.items if item.item_id != item_id
        ]
        if current > removed_index:
            self.set_highlight(current - 1)
        elif current == removed_index:
            self.set_highlight(min(current, len(self.items) - 1))
        else:
            self.set_highlight(current)

    def delete_highlighted(self) -> None:
        row = self.highlight_row
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self.set_highlight(min(row, len(self.items) - 1))

    def clear(self) -> None:
        self.raw["comparison_items"] = []
        self.set_highlight(-1)

    def move_highlight(self, delta: int) -> None:
        row = self.highlight_row
        target = row + delta
        if 0 <= row < len(self.items) and 0 <= target < len(self.items):
            self.items[row], self.items[target] = self.items[target], self.items[row]
            self.set_highlight(target)

    def rename(self, item_id: str, new_name: str) -> str:
        item = self.item_by_id(item_id)
        if item is None:
            return ""
        text = (new_name or "").strip()
        if not text:
            text = comp.comparison_item_label(item)
        item.set_label(text)
        return comp.comparison_item_label(item)

    def set_visible(self, item_id: str, visible: bool) -> None:
        item = self.item_by_id(item_id)
        if item is not None:
            item.visible = bool(visible)

    def set_color(self, item_id: str, color: str) -> None:
        item = self.item_by_id(item_id)
        if item is not None:
            item.color = color

    def sync_file_alias(self, path: Path, alias: str) -> None:
        for item in self.items:
            if item.file_path == path:
                item.rename(alias)

    def remove_file_items(self, path: Path) -> None:
        self.raw["comparison_items"] = [
            item for item in self.items if item.file_path != path
        ]
        self.set_highlight(self.highlight_row)


@dataclass
class PaletteState:
    raw: dict[str, Any]

    @property
    def schemes(self) -> dict[str, dict[str, str]]:
        return self.raw.setdefault("palette_schemes", {})

    @property
    def slot_counts(self) -> dict[str, int]:
        return self.raw.setdefault("palette_scheme_slot_counts", {})

    @property
    def active_name(self) -> str:
        name = normalize_palette_scheme_name(self.raw.get("active_palette_scheme"))
        if name not in self.schemes:
            name = next(iter(self.schemes), DEFAULT_SCHEME_NAME)
            self.raw["active_palette_scheme"] = name
        return name

    def ensure_default(self) -> None:
        self._merge_legacy_default_names()
        if not self.schemes:
            self.schemes[DEFAULT_SCHEME_NAME] = {
                str(i): color for i, color in enumerate(COMPARISON_COLORS)
            }
        default = self.schemes.setdefault(DEFAULT_SCHEME_NAME, {})
        for i, color in enumerate(COMPARISON_COLORS):
            default[str(i)] = color
        self.slot_counts.setdefault(
            DEFAULT_SCHEME_NAME,
            len(COMPARISON_COLORS),
        )
        self.slot_counts[DEFAULT_SCHEME_NAME] = max(
            int(self.slot_counts.get(DEFAULT_SCHEME_NAME, 0)),
            len(COMPARISON_COLORS),
        )
        active = normalize_palette_scheme_name(self.raw.get("active_palette_scheme"))
        if active not in self.schemes:
            self.raw["active_palette_scheme"] = DEFAULT_SCHEME_NAME
        else:
            self.raw["active_palette_scheme"] = active

    def scheme_names(self) -> list[str]:
        self.ensure_default()
        names = [name for name in self.schemes.keys() if name != DEFAULT_SCHEME_NAME]
        return [DEFAULT_SCHEME_NAME] + names

    def set_active(self, name: str) -> None:
        name = normalize_palette_scheme_name(name)
        if name in self.schemes:
            self.raw["active_palette_scheme"] = name

    def slot_count(self, name: str | None = None) -> int:
        name = normalize_palette_scheme_name(name or self.active_name)
        return int(self.slot_counts.get(name, len(self.schemes.get(name, {})) or len(COMPARISON_COLORS)))

    def colors(self, name: str | None = None, count: int | None = None) -> list[str]:
        name = normalize_palette_scheme_name(name or self.active_name)
        count = self.slot_count(name) if count is None else count
        return [
            self.color_at(index, name=name)
            for index in range(count)
        ]

    def color_at(self, index: int, name: str | None = None) -> str:
        name = normalize_palette_scheme_name(name or self.active_name)
        scheme = self.schemes.get(name, {})
        return (
            scheme.get(str(index))
            or scheme.get(index)
            or COMPARISON_COLORS[int(index) % len(COMPARISON_COLORS)]
        )

    def set_color(self, index: int, color: str) -> None:
        active = self.active_name
        self.schemes.setdefault(active, {})[str(int(index))] = normalize_hex_color(color)

    def set_count(self, count: int) -> None:
        self.slot_counts[self.active_name] = max(1, int(count))

    def save_copy(self, name: str) -> bool:
        name = normalize_palette_scheme_name(name)
        if not name or name in self.schemes:
            return False
        self.schemes[name] = {
            str(i): color for i, color in enumerate(self.colors(self.active_name))
        }
        self.slot_counts[name] = self.slot_count()
        self.raw["active_palette_scheme"] = name
        return True

    def delete(self, name: str) -> None:
        name = normalize_palette_scheme_name(name)
        if name == DEFAULT_SCHEME_NAME:
            self.reset_default()
            self.raw["active_palette_scheme"] = DEFAULT_SCHEME_NAME
            return
        if len(self.schemes) <= 1:
            return
        self.schemes.pop(name, None)
        self.slot_counts.pop(name, None)
        if self.active_name == name or name not in self.schemes:
            self.raw["active_palette_scheme"] = DEFAULT_SCHEME_NAME

    def reset_default(self) -> None:
        self.schemes[DEFAULT_SCHEME_NAME] = {
            str(i): color for i, color in enumerate(COMPARISON_COLORS)
        }
        self.slot_counts[DEFAULT_SCHEME_NAME] = len(COMPARISON_COLORS)

    def add_color(self, color: str | None = None, after_index: int | None = None) -> int:
        colors = self.colors(self.active_name)
        if after_index is None:
            index = len(colors)
        else:
            index = max(0, min(int(after_index) + 1, len(colors)))
        colors.insert(index, normalize_hex_color(color or COMPARISON_COLORS[index % len(COMPARISON_COLORS)]))
        self._replace_active_colors(colors)
        return index

    def remove_color(self, index: int) -> None:
        colors = self.colors(self.active_name)
        if len(colors) <= 1:
            return
        index = max(0, min(int(index), len(colors) - 1))
        colors.pop(index)
        self._replace_active_colors(colors)

    def move_color(self, index: int, delta: int) -> int:
        colors = self.colors(self.active_name)
        if not colors:
            return 0
        index = max(0, min(int(index), len(colors) - 1))
        target = max(0, min(index + int(delta), len(colors) - 1))
        if target != index:
            colors[index], colors[target] = colors[target], colors[index]
            self._replace_active_colors(colors)
        return target

    def reverse_colors(self) -> None:
        colors = list(reversed(self.colors(self.active_name)))
        self._replace_active_colors(colors)

    def gradient_fill(self) -> None:
        colors = self.colors(self.active_name)
        if len(colors) < 3:
            return
        first = QColorCompat(colors[0])
        last = QColorCompat(colors[-1])
        filled: list[str] = []
        span = len(colors) - 1
        for i in range(len(colors)):
            t = i / span
            r = round(first.r + (last.r - first.r) * t)
            g = round(first.g + (last.g - first.g) * t)
            b = round(first.b + (last.b - first.b) * t)
            filled.append(f"#{r:02x}{g:02x}{b:02x}")
        self._replace_active_colors(filled)

    def _replace_active_colors(self, colors: list[str]) -> None:
        active = self.active_name
        self.schemes[active] = {
            str(i): normalize_hex_color(color)
            for i, color in enumerate(colors)
        }
        self.slot_counts[active] = max(1, len(colors))

    def _merge_legacy_default_names(self) -> None:
        schemes = self.schemes
        slot_counts = self.slot_counts
        for legacy in list(LEGACY_DEFAULT_SCHEME_NAMES):
            if legacy not in schemes:
                continue
            legacy_colors = schemes.pop(legacy) or {}
            current = schemes.setdefault(DEFAULT_SCHEME_NAME, {})
            current.update({str(k): v for k, v in legacy_colors.items()})
            if legacy in slot_counts:
                slot_counts[DEFAULT_SCHEME_NAME] = max(
                    int(slot_counts.get(DEFAULT_SCHEME_NAME, 0)),
                    int(slot_counts.pop(legacy)),
                )


@dataclass
class OperationState:
    raw: dict[str, Any]

    @property
    def generation(self) -> int:
        return int(self.raw.get("_op_generation", 0))

    def bump_generation(self) -> int:
        generation = self.generation + 1
        self.raw["_op_generation"] = generation
        return generation

    def is_current(self, generation: int | None) -> bool:
        return generation is None or int(generation) == self.generation


@dataclass
class InteractionState:
    raw: dict[str, Any]

    @property
    def mode(self) -> str:
        return str(self.raw.get("interaction_mode") or "idle")

    def set_mode(self, mode: str) -> None:
        self.raw["interaction_mode"] = mode

    def enable_manual(self, *, path: Path | None, generation: int) -> None:
        self.raw["manual_mode"] = True
        self.raw["manual_file_path"] = path
        self.raw["manual_generation"] = int(generation)
        self.raw["interaction_mode"] = "manual_select"

    def disable_manual(self) -> None:
        self.raw["manual_mode"] = False
        self.raw["manual_file_path"] = None
        self.raw["manual_generation"] = None
        if self.mode == "manual_select":
            self.raw["interaction_mode"] = "idle"

    def invalidate(self) -> None:
        self.disable_manual()
        self.raw["selector"] = None

    def manual_is_current(self, *, path: Path | None, generation: int) -> bool:
        if not self.raw.get("manual_mode", False):
            return False
        return (
            self.raw.get("manual_file_path") == path
            and int(self.raw.get("manual_generation", -1)) == int(generation)
        )


class AppState:
    def __init__(self, raw: dict[str, Any] | None = None):
        self.raw = create_initial_state() if raw is None else raw
        self.files = FileState(self.raw)
        self.analysis = AnalysisState(self.raw)
        self.segments = SegmentState(self.raw)
        self.comparison = ComparisonState(self.raw)
        self.palette = PaletteState(self.raw)
        self.operations = OperationState(self.raw)
        self.interaction = InteractionState(self.raw)

    def reset_current_file(self) -> None:
        self.files.clear_current_file()

    def set_comparison_mode(self, enabled: bool) -> None:
        self.raw["comparison_mode"] = bool(enabled)

    @property
    def comparison_mode(self) -> bool:
        return bool(self.raw.get("comparison_mode", False))
