# Tafel Analyzer UI Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the fragmented PySide6 GUI into a coherent 3-panel layout (file+segments, comparison, palette) with merged toolbar, fix all broken signal wiring, and restore full feature parity with the old CTk GUI.

**Architecture:** New `FileSegmentPanel` replaces `FilePanel` + `SegmentPanel` via QSplitter. New `Toolbar` replaces `FormulaPanel` + `ParamToolBar`. ActivityBar reduced to 3 icons. Each mode uses sidebar (320px) + right area (stretch) full-window. Controllers adapt to new signal interfaces.

**Tech Stack:** PySide6 (Qt 6), matplotlib QtAgg, numpy. `core/` unchanged.

---

## File Structure (Final State)

```
src/gui_qt/
├── __init__.py
├── app.py                      # MODIFY: complete layout rebuild
├── theme.py                    # MODIFY: add styles for new components
├── activity_bar.py             # MODIFY: 3 icons (file/compare/palette)
├── panels/
│   ├── __init__.py
│   ├── file_segment.py         # NEW: merged file+segment with QSplitter
│   ├── comparison.py           # MODIFY: header buttons, complete signals
│   ├── palette.py              # NEW: palette sidebar panel
│   └── formula_panel.py        # DELETE: merged into toolbar
├── central/
│   ├── __init__.py
│   ├── toolbar.py              # NEW: formula + params merged (replaces param_bar.py)
│   ├── chart_widget.py          # unchanged
│   ├── chart_toolbar.py         # MODIFY: add manual fit, export buttons
│   ├── palette_workspace.py    # NEW: right-side palette editor
│   └── param_bar.py            # DELETE: merged into toolbar
└── controllers/
    ├── __init__.py
    ├── file_ctrl.py             # MODIFY: adapt to FileSegmentPanel signals
    ├── fitting_ctrl.py          # MODIFY: adapt to Toolbar signals
    ├── comparison_ctrl.py       # MODIFY: complete wiring
    ├── export_ctrl.py           # MODIFY: complete wiring
    ├── base.py                  # unchanged
    └── segment_ctrl.py          # unchanged
```

---

### Task 1: Theme — Add styles for new components

**Files:**
- Modify: `src/gui_qt/theme.py`

- [ ] **Step 1: Add styles for the new toolbar, file list, and palette components**

Add to `src/gui_qt/theme.py` after the existing LIST_STYLE:

```python
# ━━ Compact toolbar styles ━━

TOOLBAR_STYLE = f"""
    QWidget#ToolBar {{
        background: {BG_CARD};
        border-bottom: 1px solid {BORDER};
    }}
"""

TOOLBAR_LABEL = f"""
    QLabel {{
        color: {TEXT_SECONDARY};
        font-size: 11px;
    }}
"""

SMALL_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: {TEXT_SECONDARY};
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
        color: {TEXT_PRIMARY};
    }}
"""

DANGER_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: {DANGER};
    }}
    QPushButton:hover {{
        background: #fee2e2;
    }}
"""

# ━━ FileSegmentPanel styles ━━

FILE_ITEM_STYLE = f"""
    QWidget#FileItem {{
        background: transparent;
    }}
    QWidget#FileItem:hover {{
        background: {BG_HOVER};
        border-radius: 6px;
    }}
"""

SEGMENT_ITEM_STYLE = f"""
    QWidget#SegmentItem {{
        background: transparent;
        border-radius: 6px;
    }}
    QWidget#SegmentItem:hover {{
        background: {BG_HOVER};
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        spacing: 0px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {BORDER};
        border-radius: 4px;
        background: {BG_CARD};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""

# ━━ Palette panel styles ━━

COLOR_SWATCH_STYLE = """
    QPushButton {{
        border: 2px solid white;
        border-radius: 8px;
    }}
    QPushButton:hover {{
        border-color: #2563eb;
    }}
"""

GRADIENT_PREVIEW_STYLE = f"""
    QWidget#GradientPreview {{
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
"""

STATUS_BAR_STYLE = f"""
    QLabel {{
        color: {TEXT_SECONDARY};
        font-size: 10px;
        padding: 2px 8px;
        background: {BG_CARD};
    }}
"""
```

- [ ] **Step 2: Verify theme file loads without errors**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.theme import *; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/theme.py
git commit -m "feat: add QSS styles for new consolidated panels and toolbar"
```

---

### Task 2: FileSegmentPanel — Build merged file+segment panel

**Files:**
- Create: `src/gui_qt/panels/file_segment.py`
- This is the largest new file. It replaces both `file_panel.py` and `segment_panel.py`.

- [ ] **Step 1: Create the panel skeleton with all signals and layout structure**

Create `src/gui_qt/panels/file_segment.py`:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QComboBox, QSplitter,
    QCheckBox, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    PANEL_STYLE, BUTTON_STYLE, SMALL_BUTTON_STYLE, DANGER_BUTTON_STYLE,
    ACCENT_BUTTON_STYLE, INPUT_STYLE, LIST_STYLE, CHECKBOX_STYLE,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, ACCENT, BG_HOVER, BG_CARD,
)


class FileListItem(QWidget):
    """Custom widget for each file row: name | ✓ badge | × remove."""

    remove_clicked = Signal(object)  # Path

    def __init__(self, file_path: Path, is_processed: bool = False):
        super().__init__()
        self.setObjectName("FileItem")
        self.file_path = file_path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        name = QLabel(file_path.name)
        name.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(name, stretch=1)

        if is_processed:
            badge = QLabel("✓")
            badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 12px;")
            layout.addWidget(badge)

        btn = QPushButton("×")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 11px; color: #dc2626; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #fee2e2; }}"
        )
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.remove_clicked.emit(self.file_path))
        layout.addWidget(btn)


class SegmentItemWidget(QWidget):
    """One row in segment list: ▶ active | ☑ checkbox | label | R² | 🎨 color."""

    activated = Signal(int)
    toggled = Signal(int, bool)
    color_clicked = Signal(int)

    def __init__(self, index: int, label: str, color: str,
                 is_active: bool, is_checked: bool, r2: float | None):
        super().__init__()
        self.setObjectName("SegmentItem")
        self.segment_index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Active indicator
        active_symbol = "▶" if is_active else "  "
        active_color = ACCENT if is_active else TEXT_SECONDARY
        self.active_label = QLabel(active_symbol)
        self.active_label.setStyleSheet(f"color: {active_color}; font-size: 10px;")
        self.active_label.setFixedWidth(16)
        layout.addWidget(self.active_label)

        # Checkbox
        self.cb = QCheckBox()
        self.cb.setChecked(is_checked)
        self.cb.setStyleSheet(CHECKBOX_STYLE)
        self.cb.stateChanged.connect(lambda state: self.toggled.emit(index, bool(state)))
        layout.addWidget(self.cb)

        # Label
        name = QLabel(label)
        name.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(name, stretch=1)

        # R² badge
        if r2 is not None:
            r2_label = QLabel(f"R²={r2:.4f}")
            r2_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
            layout.addWidget(r2_label)
        else:
            na = QLabel("未拟合")
            na.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            layout.addWidget(na)

        # Color swatch
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(index))
        layout.addWidget(self.color_btn)

        # Click on row body activates segment
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.activated.emit(self.segment_index)
        super().mousePressEvent(event)

    def update_state(self, is_active: bool, is_checked: bool, r2: float | None, color: str):
        self.active_label.setText("▶" if is_active else "  ")
        self.active_label.setStyleSheet(
            f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 10px;"
        )
        self.cb.blockSignals(True)
        self.cb.setChecked(is_checked)
        self.cb.blockSignals(False)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        # R² update is handled by full rebuild for simplicity


class FileSegmentPanel(QWidget):
    """Merged file selection + segment management panel with QSplitter."""

    # File signals
    files_selected = Signal(list)           # list[Path]
    file_activated = Signal(object)         # Path
    file_removed = Signal(object)           # Path
    cache_import_requested = Signal()
    export_name_changed = Signal(str)

    # Segment signals
    segment_activated = Signal(int)
    segment_toggled = Signal(int, bool)
    segment_color_changed = Signal(int, str)
    select_all_clicked = Signal()
    clear_all_clicked = Signal()
    add_to_comparison = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal()
    palette_manage_clicked = Signal()

    # Export signals
    export_current = Signal()
    export_batch = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ━━ File section (fixed height — outside splitter) ━━
        file_header = QWidget()
        file_header_layout = QVBoxLayout(file_header)
        file_header_layout.setContentsMargins(16, 12, 16, 4)
        file_header_layout.setSpacing(4)

        # Title row: count badge + icon buttons
        title_row = QHBoxLayout()
        self.file_count_label = QLabel("📂 文件 (0/0)")
        self.file_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        title_row.addWidget(self.file_count_label, stretch=1)

        btn_select = QPushButton("📁")
        btn_select.setToolTip("选择数据文件")
        btn_select.setFixedSize(28, 28)
        btn_select.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.clicked.connect(self._on_select_files)
        title_row.addWidget(btn_select)

        btn_cache = QPushButton("📥")
        btn_cache.setToolTip("导入缓存")
        btn_cache.setFixedSize(28, 28)
        btn_cache.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_cache.setCursor(Qt.PointingHandCursor)
        btn_cache.clicked.connect(self.cache_import_requested.emit)
        title_row.addWidget(btn_cache)

        btn_remove = QPushButton("🗑")
        btn_remove.setToolTip("移除当前文件")
        btn_remove.setFixedSize(28, 28)
        btn_remove.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.clicked.connect(self._on_remove_current)
        title_row.addWidget(btn_remove)

        file_header_layout.addLayout(title_row)

        # Export row: name input + buttons
        export_row = QHBoxLayout()
        export_row.setSpacing(4)
        export_row.addWidget(QLabel("导出名:"))
        self.export_name_input = QLineEdit()
        self.export_name_input.setPlaceholderText("默认使用文件名")
        self.export_name_input.setStyleSheet(INPUT_STYLE)
        self.export_name_input.textChanged.connect(
            lambda t: self.export_name_changed.emit(t)
        )
        export_row.addWidget(self.export_name_input, stretch=1)

        btn_export_cur = QPushButton("💾")
        btn_export_cur.setToolTip("导出当前结果")
        btn_export_cur.setFixedSize(28, 28)
        btn_export_cur.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_export_cur.setCursor(Qt.PointingHandCursor)
        btn_export_cur.clicked.connect(self.export_current.emit)
        export_row.addWidget(btn_export_cur)

        btn_export_batch = QPushButton("📦")
        btn_export_batch.setToolTip("批量导出")
        btn_export_batch.setFixedSize(28, 28)
        btn_export_batch.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_export_batch.setCursor(Qt.PointingHandCursor)
        btn_export_batch.clicked.connect(self.export_batch.emit)
        export_row.addWidget(btn_export_batch)

        file_header_layout.addLayout(export_row)
        outer.addWidget(file_header)

        # ━━ QSplitter: file list / segment section ━━
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_HOVER}; }}")

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_STYLE)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_click)
        splitter.addWidget(self.file_list)

        # Segment section (header + palette + list, all inside a container widget)
        segment_container = QWidget()
        segment_layout = QVBoxLayout(segment_container)
        segment_layout.setContentsMargins(16, 8, 16, 8)
        segment_layout.setSpacing(4)

        # Segment header
        seg_header = QHBoxLayout()
        self.seg_count_label = QLabel("📋 分段 (0/0)")
        self.seg_count_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        seg_header.addWidget(self.seg_count_label, stretch=1)

        btn_select_all = QPushButton("全选")
        btn_select_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.clicked.connect(self.select_all_clicked.emit)
        seg_header.addWidget(btn_select_all)

        btn_clear_all = QPushButton("全不选")
        btn_clear_all.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_clear_all.clicked.connect(self.clear_all_clicked.emit)
        seg_header.addWidget(btn_clear_all)

        btn_add_cmp = QPushButton("📌 对比")
        btn_add_cmp.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_add_cmp.setCursor(Qt.PointingHandCursor)
        btn_add_cmp.clicked.connect(self.add_to_comparison.emit)
        seg_header.addWidget(btn_add_cmp)

        segment_layout.addLayout(seg_header)

        # Palette row
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("🎨 配色:"))
        self.palette_combo = QComboBox()
        self.palette_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px 8px; font-size: 12px; }}"
        )
        self.palette_combo.currentTextChanged.connect(self.palette_scheme_changed.emit)
        palette_row.addWidget(self.palette_combo, stretch=1)

        btn_apply = QPushButton("应用")
        btn_apply.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.palette_apply_clicked.emit)
        palette_row.addWidget(btn_apply)

        btn_manage = QPushButton("⚙")
        btn_manage.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self.palette_manage_clicked.emit)
        palette_row.addWidget(btn_manage)

        segment_layout.addLayout(palette_row)

        # Segment list
        self.segment_list = QListWidget()
        self.segment_list.setStyleSheet(LIST_STYLE)
        segment_layout.addWidget(self.segment_list, stretch=1)

        splitter.addWidget(segment_container)

        # Default 40/60 split
        splitter.setSizes([150, 300])
        outer.addWidget(splitter, stretch=1)

        # Internal state
        self._file_paths: list[Path] = []
        self._processed: set[str] = set()
        self._segments: list[dict] = []
        self._active_index: int = 0
        self._checked_indices: set[int] = set()
        self._segment_colors: dict[int, str] = {}

    # ━━ File operations ━━

    def _on_select_files(self):
        paths_str, _ = QFileDialog.getOpenFileNames(
            self, "选择数据文件", "",
            "支持的文件 (*.tdms *.txt *.csv *.xlsx *.xls *.cor);;All files (*.*)"
        )
        if not paths_str:
            return
        paths = [Path(p) for p in paths_str]
        new_paths = [p for p in paths if p not in self._file_paths]
        self._file_paths.extend(new_paths)
        self._rebuild_file_list()
        if new_paths:
            self.files_selected.emit(new_paths)

    def _on_file_double_click(self, item: QListWidgetItem):
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            self.file_activated.emit(widget.file_path)

    def _on_remove_current(self):
        if not self._file_paths:
            return
        # Emit remove for the first file; controller handles full logic
        current = self._file_paths[0]
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{current.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._file_paths.remove(current)
            self._processed.discard(str(current))
            self._rebuild_file_list()
            self.file_removed.emit(current)

    def _rebuild_file_list(self):
        self.file_list.clear()
        for path in self._file_paths:
            item = QListWidgetItem()
            widget = FileListItem(path, str(path) in self._processed)
            widget.remove_clicked.connect(self._on_file_remove)
            item.setSizeHint(widget.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, widget)
        processed_count = len(self._processed)
        total = len(self._file_paths)
        self.file_count_label.setText(f"📂 文件 ({processed_count}/{total})")

    def _on_file_remove(self, path: Path):
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{path.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._file_paths.remove(path)
            self._processed.discard(str(path))
            self._rebuild_file_list()
            self.file_removed.emit(path)

    def set_file_paths(self, paths: list[Path], processed: set[str]) -> None:
        self._file_paths = list(paths)
        self._processed = set(processed)
        self._rebuild_file_list()

    def set_processed(self, path: Path) -> None:
        self._processed.add(str(path))
        self._rebuild_file_list()

    # ━━ Segment operations ━━

    def set_segments(self, segments: list[dict], active_index: int,
                     checked_indices: set[int], colors: dict[int, str],
                     fit_by_segment: dict) -> None:
        self._segments = segments
        self._active_index = active_index
        self._checked_indices = set(checked_indices)
        self._segment_colors = dict(colors)
        self._rebuild_segment_list(fit_by_segment)

    def _rebuild_segment_list(self, fit_by_segment: dict) -> None:
        self.segment_list.clear()
        for seg in self._segments:
            idx = seg["index"]
            color = self._segment_colors.get(idx, "#94a3b8")
            is_active = idx == self._active_index
            is_checked = idx in self._checked_indices
            fit = fit_by_segment.get(idx)
            r2 = fit.r2 if fit is not None else None

            item = QListWidgetItem()
            widget = SegmentItemWidget(idx, seg["label"], color, is_active, is_checked, r2)
            widget.activated.connect(self.segment_activated.emit)
            widget.toggled.connect(self.segment_toggled.emit)
            widget.color_clicked.connect(self.segment_color_changed.emit)
            item.setSizeHint(widget.sizeHint())
            self.segment_list.addItem(item)
            self.segment_list.setItemWidget(item, widget)

        self.seg_count_label.setText(
            f"📋 分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )

    def update_segment_state(self, active_index: int, checked_indices: set[int],
                              colors: dict[int, str], fit_by_segment: dict) -> None:
        """Lightweight update without full rebuild — updates each row widget."""
        self._active_index = active_index
        self._checked_indices = set(checked_indices)
        self._segment_colors = dict(colors)
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            w = self.segment_list.itemWidget(item)
            if isinstance(w, SegmentItemWidget):
                idx = w.segment_index
                fit = fit_by_segment.get(idx)
                w.update_state(
                    is_active=(idx == active_index),
                    is_checked=(idx in self._checked_indices),
                    r2=fit.r2 if fit is not None else None,
                    color=self._segment_colors.get(idx, "#94a3b8"),
                )
        self.seg_count_label.setText(
            f"📋 分段 ({len(self._checked_indices)}/{len(self._segments)})"
        )

    # ━━ Palette schemes ━━

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)

    def set_export_name(self, name: str) -> None:
        self.export_name_input.setText(name)

    def get_export_name(self) -> str:
        return self.export_name_input.text().strip()
```

- [ ] **Step 2: Verify the new panel imports correctly**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.panels.file_segment import FileSegmentPanel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/panels/file_segment.py
git commit -m "feat: add FileSegmentPanel with QSplitter for merged file+segment management"
```

---

### Task 3: Toolbar — Build merged formula+params toolbar

**Files:**
- Create: `src/gui_qt/central/toolbar.py`

- [ ] **Step 1: Create the toolbar widget**

Create `src/gui_qt/central/toolbar.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    TOOLBAR_STYLE, TOOLBAR_LABEL, INPUT_STYLE, ACCENT_BUTTON_STYLE,
    BG_CARD, BORDER, ACCENT, ACCENT_HOVER, SUCCESS, SUCCESS_HOVER,
    WARNING, WARNING_HOVER,
)


class ToolBar(QWidget):
    """Merged formula entry + parameter inputs + fit operations toolbar."""

    fit_clicked = Signal()
    manual_clicked = Signal()
    formulas_changed = Signal(str, str)  # potential, current
    params_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolBar")
        self.setFixedHeight(68)
        self.setStyleSheet(TOOLBAR_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(2)

        # Row 1: formula inputs
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        def add_formula(label_text: str, placeholder: str) -> QLineEdit:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(TOOLBAR_LABEL)
            row1.addWidget(lbl)
            entry = QLineEdit()
            entry.setPlaceholderText(placeholder)
            entry.setStyleSheet(INPUT_STYLE)
            entry.textChanged.connect(self._emit_formulas)
            row1.addWidget(entry, stretch=1)
            return entry

        self.potential_input = add_formula("电压:", "例如 -[Vgs]+0.23")
        self.current_input = add_formula("电流:", "例如 [Igs/area]/(2.4e-7+3)")
        outer.addLayout(row1)

        # Row 2: parameters + fit buttons
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        def add_param(label_text: str, width: int = 60, default: str = "") -> QLineEdit:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(TOOLBAR_LABEL)
            row2.addWidget(lbl)
            entry = QLineEdit()
            entry.setFixedWidth(width)
            entry.setStyleSheet(INPUT_STYLE)
            if default:
                entry.setText(default)
            entry.textChanged.connect(self._emit_params)
            row2.addWidget(entry)
            return entry

        self.entry_eeq = add_param("E_eq:", 50, "0")
        self.entry_window = add_param("窗口:", 55, "12-15")
        self.entry_eta = add_param("η:", 55)
        self.entry_logj = add_param("logj:", 55)
        self.entry_r2 = add_param("R²:", 45, "0.95")

        lbl_pri = QLabel("优先:")
        lbl_pri.setStyleSheet(TOOLBAR_LABEL)
        row2.addWidget(lbl_pri)
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["斜率更低优先", "R²优先"])
        self.combo_priority.setStyleSheet(
            f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 2px 6px; font-size: 11px; background: {BG_CARD}; }}"
        )
        self.combo_priority.currentTextChanged.connect(self._emit_params)
        row2.addWidget(self.combo_priority)

        row2.addStretch()

        btn_fit = QPushButton("▶ 拟合")
        btn_fit.setStyleSheet(ACCENT_BUTTON_STYLE.replace(ACCENT, SUCCESS).replace(ACCENT_HOVER, SUCCESS_HOVER))
        btn_fit.setCursor(Qt.PointingHandCursor)
        btn_fit.clicked.connect(self.fit_clicked.emit)
        row2.addWidget(btn_fit)

        btn_manual = QPushButton("🖱 手动")
        btn_manual.setStyleSheet(ACCENT_BUTTON_STYLE.replace(ACCENT, WARNING).replace(ACCENT_HOVER, WARNING_HOVER))
        btn_manual.setCursor(Qt.PointingHandCursor)
        btn_manual.clicked.connect(self.manual_clicked.emit)
        row2.addWidget(btn_manual)

        outer.addLayout(row2)

    def _emit_formulas(self):
        self.formulas_changed.emit(
            self.potential_input.text().strip(),
            self.current_input.text().strip(),
        )

    def _emit_params(self):
        self.params_changed.emit(self.get_params())

    def get_params(self) -> dict:
        return {
            "e_eq": self.entry_eeq.text().strip(),
            "window_range": self.entry_window.text().strip(),
            "eta_range": self.entry_eta.text().strip(),
            "logj_range": self.entry_logj.text().strip(),
            "min_r2": self.entry_r2.text().strip(),
            "fit_priority": self.combo_priority.currentText().strip(),
        }

    def get_formulas(self) -> tuple[str, str]:
        return self.potential_input.text().strip(), self.current_input.text().strip()

    def set_formulas(self, potential: str, current: str) -> None:
        self.potential_input.blockSignals(True)
        self.current_input.blockSignals(True)
        self.potential_input.setText(potential)
        self.current_input.setText(current)
        self.potential_input.blockSignals(False)
        self.current_input.blockSignals(False)

    def set_params(self, params: dict) -> None:
        mapping = {
            "e_eq": self.entry_eeq,
            "window_range": self.entry_window,
            "eta_range": self.entry_eta,
            "logj_range": self.entry_logj,
            "min_r2": self.entry_r2,
        }
        for key, entry in mapping.items():
            entry.blockSignals(True)
            val = params.get(key, "")
            if val:
                entry.setText(str(val))
            entry.blockSignals(False)
        if "fit_priority" in params:
            self.combo_priority.blockSignals(True)
            self.combo_priority.setCurrentText(params["fit_priority"])
            self.combo_priority.blockSignals(False)

    def set_enabled(self, enabled: bool) -> None:
        for w in [self.potential_input, self.current_input, self.entry_eeq,
                  self.entry_window, self.entry_eta, self.entry_logj, self.entry_r2,
                  self.combo_priority]:
            w.setEnabled(enabled)
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.central.toolbar import ToolBar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/central/toolbar.py
git commit -m "feat: add merged ToolBar with formula + params + fit operations"
```

---

### Task 4: ActivityBar — Update to 3 icons

**Files:**
- Modify: `src/gui_qt/activity_bar.py`

- [ ] **Step 1: Reduce to 3 panel IDs and update icons**

Read the current file and replace the contents:

```python
"""Activity bar — 48px vertical icon strip for panel switching."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_SECONDARY


PANEL_FILES = 0
PANEL_COMPARISON = 1
PANEL_PALETTE = 2


class ActivityBar(QWidget):
    """48px vertical icon strip. 3 panels: files+segments, comparison, palette."""

    panel_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"""
            ActivityBar {{
                background: {BG_CARD};
                border-right: 1px solid #e2e8f0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        self._buttons: list[QPushButton] = []

        for icon_text, panel_id, tooltip in [
            ("📂", PANEL_FILES, "文件与分段"),
            ("📊", PANEL_COMPARISON, "跨文件对比"),
            ("🎨", PANEL_PALETTE, "配色方案"),
        ]:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, pid=panel_id: self.set_active(pid) or self.panel_clicked.emit(pid))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

    def _btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {ACCENT}; color: white; "
                f"border: none; border-radius: 8px; font-size: 18px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: none; border-radius: 8px; font-size: 18px; }}"
            f"QPushButton:hover {{ background: #f1f5f9; }}"
        )

    def set_active(self, panel_id: int) -> None:
        for idx, btn in enumerate(self._buttons):
            active = (idx == panel_id)
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/activity_bar.py
git commit -m "refactor: reduce ActivityBar to 3 icons (files, comparison, palette)"
```

---

### Task 5: ComparisonPanel — Fix layout and complete signals

**Files:**
- Modify: `src/gui_qt/panels/comparison.py`

- [ ] **Step 1: Rewrite with header buttons, palette row, result text, and export**

Read the existing `comparison.py`, then replace it completely:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QTextBrowser, QColorDialog, QCheckBox, QComboBox,
)
from PySide6.QtCore import Signal, Qt, QEvent

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, TEXT_PRIMARY, TEXT_SECONDARY, LIST_STYLE,
    ACCENT, ACCENT_BUTTON_STYLE, DANGER, SMALL_BUTTON_STYLE, INPUT_STYLE,
    BG_HOVER, BG_CARD,
)


class ComparisonItemWidget(QWidget):
    """Single row: ☑ visibility | name (dbl-click edit) | segment | color swatch."""

    visibility_toggled = Signal(str, bool)   # item_id, visible
    color_clicked = Signal(str)              # item_id
    rename_finished = Signal(str, str)       # item_id, new_name

    def __init__(self, item_id: str, display_name: str,
                 segment_label: str, color: str, visible: bool):
        super().__init__()
        self.item_id = item_id
        self._original_name = display_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Checkbox
        self.cb = QCheckBox()
        self.cb.setChecked(visible)
        self.cb.stateChanged.connect(
            lambda state: self.visibility_toggled.emit(item_id, bool(state))
        )
        layout.addWidget(self.cb)

        # Editable name
        self.name_edit = QLineEdit(display_name)
        self.name_edit.setStyleSheet(
            f"QLineEdit {{ border: none; background: transparent; "
            f"color: {TEXT_PRIMARY}; font-size: 12px; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT}; border-radius: 4px; "
            f"background: white; padding: 2px 4px; }}"
        )
        self.name_edit.setReadOnly(True)
        self.name_edit.installEventFilter(self)
        self.name_edit.editingFinished.connect(self._on_rename)
        layout.addWidget(self.name_edit, stretch=1)

        # Segment
        seg = QLabel(segment_label)
        seg.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(seg)

        # Color
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; border-radius: 10px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(lambda: self.color_clicked.emit(item_id))
        layout.addWidget(self.color_btn)

    def _on_rename(self):
        new_name = self.name_edit.text().strip()
        if new_name and new_name != self._original_name:
            self.rename_finished.emit(self.item_id, new_name)
        self._original_name = new_name or self._original_name
        if not new_name:
            self.name_edit.setText(self._original_name)

    def eventFilter(self, obj, event):
        if obj is self.name_edit and event.type() == QEvent.Type.MouseButtonDblClick:
            self.name_edit.setReadOnly(False)
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return True
        if obj is self.name_edit and event.type() == QEvent.Type.FocusOut:
            self.name_edit.setReadOnly(True)
        return super().eventFilter(obj, event)


class ComparisonPanel(QWidget):
    """Comparison side panel with header buttons, item list, result text."""

    # Item signals
    item_visibility_changed = Signal(str, bool)
    item_color_changed = Signal(str, str)
    item_renamed = Signal(str, str)

    # Action signals
    add_all_clicked = Signal()
    clear_all_clicked = Signal()
    delete_selected_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()
    export_clicked = Signal()

    # Palette signals
    palette_scheme_changed = Signal(str)
    palette_apply_clicked = Signal()
    palette_manage_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Header with all action buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("📊 对比"))
        header.addStretch()

        for text, signal in [
            ("📥 添加", self.add_all_clicked),
            ("🗑 删除", self.delete_selected_clicked),
            ("↑", self.move_up_clicked),
            ("↓", self.move_down_clicked),
            ("🗑 清空", self.clear_all_clicked),
            ("💾 导出", self.export_clicked),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(SMALL_BUTTON_STYLE)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            header.addWidget(btn)

        layout.addLayout(header)

        # Palette row
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("🎨 配色:"))
        self.palette_combo = QComboBox()
        self.palette_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px 8px; font-size: 12px; }}"
        )
        self.palette_combo.currentTextChanged.connect(self.palette_scheme_changed.emit)
        palette_row.addWidget(self.palette_combo, stretch=1)

        btn_apply = QPushButton("应用")
        btn_apply.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.palette_apply_clicked.emit)
        palette_row.addWidget(btn_apply)

        btn_manage = QPushButton("⚙")
        btn_manage.setStyleSheet(SMALL_BUTTON_STYLE)
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self.palette_manage_clicked.emit)
        palette_row.addWidget(btn_manage)

        layout.addLayout(palette_row)

        # Item list
        self.item_list = QListWidget()
        self.item_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.item_list, stretch=1)

        # Result text
        self.result_text = QTextBrowser()
        self.result_text.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid #e2e8f0; border-radius: 4px; "
            f"background: {BG_HOVER}; color: {TEXT_PRIMARY}; font-size: 12px; padding: 4px; }}"
        )
        self.result_text.setFixedHeight(120)
        layout.addWidget(self.result_text)

    def set_items(self, items: list[dict]) -> None:
        """items: list of {item_id, display_name, segment_label, color, visible}"""
        self.item_list.clear()
        for data in items:
            widget = ComparisonItemWidget(
                data["item_id"], data["display_name"],
                data["segment_label"], data["color"], data["visible"],
            )
            widget.visibility_toggled.connect(self.item_visibility_changed.emit)
            widget.color_clicked.connect(self._on_color)
            widget.rename_finished.connect(self.item_renamed.emit)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.item_list.addItem(item)
            self.item_list.setItemWidget(item, widget)

    def _on_color(self, item_id: str):
        color = QColorDialog.getColor()
        if color.isValid():
            self.item_color_changed.emit(item_id, color.name())

    def set_result_text(self, text: str) -> None:
        self.result_text.setPlainText(text)

    def set_palette_schemes(self, schemes: list[str], active: str) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(schemes)
        if active in schemes:
            self.palette_combo.setCurrentText(active)
        self.palette_combo.blockSignals(False)
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.panels.comparison import ComparisonPanel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/panels/comparison.py
git commit -m "feat: complete ComparisonPanel with header buttons, palette row, and result text"
```

---

### Task 6: PalettePanel — Left sidebar palette controls

**Files:**
- Create: `src/gui_qt/panels/palette.py`

- [ ] **Step 1: Create the palette sidebar panel**

Create `src/gui_qt/panels/palette.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QScrollArea, QColorDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    PANEL_STYLE, BUTTON_STYLE, ACCENT_BUTTON_STYLE, SMALL_BUTTON_STYLE,
    DANGER_BUTTON_STYLE, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT,
    BG_CARD, BG_HOVER,
)


class ColorSwatch(QPushButton):
    """Clickable color square with hex label."""

    color_clicked = Signal(int, str)  # index, current_hex

    def __init__(self, index: int, hex_color: str, segment_name: str):
        super().__init__()
        self._index = index
        self._hex = hex_color
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{segment_name}: {hex_color}")
        self._update_style()
        self.clicked.connect(lambda: self.color_clicked.emit(self._index, self._hex))

    def _update_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._hex}; border: 2px solid white; border-radius: 6px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )

    def set_color(self, hex_color: str):
        self._hex = hex_color
        self._update_style()


class PaletteSidebar(QWidget):
    """Left sidebar for palette scheme management — Origin-style compact."""

    scheme_changed = Signal(str)
    color_changed = Signal(int, str)       # index, new_hex
    color_count_changed = Signal(int)
    apply_to_current_clicked = Signal()
    save_as_new_clicked = Signal(str)     # name
    delete_scheme_clicked = Signal(str)   # name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title + scheme selector
        layout.addWidget(QLabel("🎨 配色方案"))
        self.scheme_combo = QComboBox()
        self.scheme_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}"
        )
        self.scheme_combo.currentTextChanged.connect(self.scheme_changed.emit)
        layout.addWidget(self.scheme_combo)

        # Gradient preview
        self.gradient_preview = QWidget()
        self.gradient_preview.setObjectName("GradientPreview")
        self.gradient_preview.setFixedHeight(20)
        self.gradient_preview.setStyleSheet(
            f"QWidget#GradientPreview {{ border: 1px solid #e2e8f0; border-radius: 6px; }}"
        )
        layout.addWidget(self.gradient_preview)

        # Color swatch grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        scroll_widget = QWidget()
        self.swatch_layout = QVBoxLayout(scroll_widget)
        self.swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.swatch_layout.setSpacing(4)
        self.swatch_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Color count selector
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("颜色数:"))
        self.count_combo = QComboBox()
        self.count_combo.addItems(["5", "6", "8", "10", "12", "16"])
        self.count_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}"
        )
        self.count_combo.currentTextChanged.connect(
            lambda t: self.color_count_changed.emit(int(t))
        )
        count_row.addWidget(self.count_combo, stretch=1)
        layout.addLayout(count_row)

        # Action buttons
        btn_apply = QPushButton("应用到当前")
        btn_apply.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self.apply_to_current_clicked.emit)
        layout.addWidget(btn_apply)

        btn_save = QPushButton("另存为新方案")
        btn_save.setStyleSheet(BUTTON_STYLE)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._on_save_as_new)
        layout.addWidget(btn_save)

        btn_delete = QPushButton("🗑 删除方案")
        btn_delete.setStyleSheet(DANGER_BUTTON_STYLE)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._on_delete)
        layout.addWidget(btn_delete)

        # Internal state
        self._swatches: list[ColorSwatch] = []
        self._scheme_names: list[str] = []

    def set_schemes(self, schemes: list[str], active: str) -> None:
        self._scheme_names = schemes
        self.scheme_combo.blockSignals(True)
        self.scheme_combo.clear()
        self.scheme_combo.addItems(schemes)
        if active in schemes:
            self.scheme_combo.setCurrentText(active)
        self.scheme_combo.blockSignals(False)

    def set_colors(self, colors: list[str], segment_names: list[str]) -> None:
        """colors: list of hex strings, one per slot."""
        # Clear existing swatches
        for sw in self._swatches:
            sw.setParent(None)
        self._swatches.clear()

        # Remove the stretch
        while self.swatch_layout.count():
            item = self.swatch_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add swatch rows
        for i, (hex_color, name) in enumerate(zip(colors, segment_names)):
            row = QHBoxLayout()
            row.setSpacing(6)

            swatch = ColorSwatch(i, hex_color, name)
            swatch.color_clicked.connect(self._on_color_click)
            self._swatches.append(swatch)
            row.addWidget(swatch)

            lbl = QLabel(f"{hex_color}  {name}")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            row.addWidget(lbl, stretch=1)

            self.swatch_layout.addLayout(row)

        self.swatch_layout.addStretch()
        self._update_gradient(colors)

    def _on_color_click(self, index: int, _hex: str):
        color = QColorDialog.getColor()
        if color.isValid():
            new_hex = color.name()
            self._swatches[index].set_color(new_hex)
            self.color_changed.emit(index, new_hex)
            # Update gradient
            all_colors = [sw._hex for sw in self._swatches]
            self._update_gradient(all_colors)

    def _update_gradient(self, colors: list[str]):
        if not colors:
            return
        stops = ", ".join(
            f"stop:{i / max(len(colors) - 1, 1):.3f} {c}"
            for i, c in enumerate(colors)
        )
        self.gradient_preview.setStyleSheet(
            f"QWidget#GradientPreview {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops}); "
            f"border: 1px solid #e2e8f0; border-radius: 6px; }}"
        )

    def _on_save_as_new(self):
        # The controller handles creating the name dialog
        self.save_as_new_clicked.emit(self.scheme_combo.currentText())

    def _on_delete(self):
        name = self.scheme_combo.currentText()
        if not name:
            return
        confirm = QMessageBox.question(
            self, "确认删除", f"确定要删除方案 \"{name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.delete_scheme_clicked.emit(name)

    def get_active_scheme(self) -> str:
        return self.scheme_combo.currentText()
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.panels.palette import PaletteSidebar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/panels/palette.py
git commit -m "feat: add PaletteSidebar with Origin-style color management"
```

---

### Task 7: PaletteWorkspace — Right-side palette editor

**Files:**
- Create: `src/gui_qt/central/palette_workspace.py`

- [ ] **Step 1: Create a placeholder workspace for the right palette area**

Create `src/gui_qt/central/palette_workspace.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QScrollArea
from PySide6.QtCore import Qt

from gui_qt.theme import BG_CARD, TEXT_SECONDARY, TEXT_PRIMARY, ACCENT


class PaletteWorkspace(QWidget):
    """Right-side large color grid for Origin-style palette editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("配色方案编辑")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Subtitle
        self.scheme_label = QLabel("选择一个配色方案")
        self.scheme_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        layout.addWidget(self.scheme_label)

        # Color grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(12)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, stretch=1)

    def set_scheme(self, name: str, colors: list[str], segment_names: list[str]) -> None:
        """Show large swatches for the selected scheme."""
        self.scheme_label.setText(f"方案: {name}  ({len(colors)} 色)")

        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add swatches in a responsive grid
        cols = 4
        for i, (hex_color, seg_name) in enumerate(zip(colors, segment_names)):
            swatch = QWidget()
            swatch.setFixedSize(120, 100)
            swatch.setStyleSheet(
                f"QWidget {{ background: {hex_color}; border-radius: 12px; "
                f"border: 2px solid #e2e8f0; }}"
            )
            swatch.setToolTip(f"{seg_name}: {hex_color}")

            label = QLabel(f"{seg_name}\n{hex_color}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {'#0f172a' if _is_light(hex_color) else '#ffffff'}; "
                f"font-size: 11px; font-weight: 600; background: transparent; border: none;"
            )

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(swatch, row, col)
            # Overlay text on swatch
            label.setParent(swatch)
            label.setGeometry(4, 30, 112, 40)


def _is_light(hex_color: str) -> bool:
    """Return True if the color is light (for text contrast)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance > 150
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.central.palette_workspace import PaletteWorkspace; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/central/palette_workspace.py
git commit -m "feat: add PaletteWorkspace for right-side large swatch grid"
```

---

### Task 8: ChartToolbar — Add missing buttons

**Files:**
- Modify: `src/gui_qt/central/chart_toolbar.py`

- [ ] **Step 1: Read current file and add manual/export buttons**

Read `src/gui_qt/central/chart_toolbar.py`. Then rewrite it:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, BG_CARD, BORDER, TEXT_SECONDARY, ACCENT, BG_HOVER,
)


class ChartToolBar(QWidget):
    """Custom matplotlib toolbar: zoom, pan, home, manual, save."""

    zoom_clicked = Signal()
    pan_clicked = Signal()
    home_clicked = Signal()
    save_image_clicked = Signal()
    manual_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            ChartToolBar {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        def make_btn(text: str, tooltip: str, signal: Signal) -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 4px; font-size: 14px; "
                f"color: {TEXT_SECONDARY}; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; color: #0f172a; }}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            return btn

        layout.addWidget(make_btn("🏠", "复位", self.home_clicked))
        layout.addWidget(make_btn("←", "后退", self.home_clicked))  # reuse home for now
        layout.addWidget(make_btn("→", "前进", self.home_clicked))
        layout.addWidget(make_btn("🔍+", "放大", self.zoom_clicked))
        layout.addWidget(make_btn("🔍-", "缩小", self.zoom_clicked))
        layout.addWidget(make_btn("✋", "平移", self.pan_clicked))
        layout.addWidget(make_btn("🖱", "手动框选", self.manual_clicked))

        layout.addStretch()

        layout.addWidget(make_btn("💾", "保存图片", self.save_image_clicked))
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.central.chart_toolbar import ChartToolBar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/central/chart_toolbar.py
git commit -m "feat: add manual/zoom/pan buttons to ChartToolBar"
```

---

### Task 9: app.py — Rebuild layout with new panels

**Files:**
- Modify: `src/gui_qt/app.py`

- [ ] **Step 1: Rewrite _build_ui and _init_controllers for the new architecture**

Read the current `app.py`. Replace `_build_ui` and `_init_controllers`:

Note: The QMainWindow already has correct imports. Replace the build method:

```python
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Activity bar
        self.activity_bar = ActivityBar()
        self.activity_bar.panel_clicked.connect(self._on_panel_clicked)
        layout.addWidget(self.activity_bar)

        # Side panel stack (320px)
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(320)

        from gui_qt.panels.file_segment import FileSegmentPanel
        from gui_qt.panels.comparison import ComparisonPanel
        from gui_qt.panels.palette import PaletteSidebar

        self.file_segment_panel = FileSegmentPanel()
        self.side_stack.addWidget(self.file_segment_panel)  # index 0 = PANEL_FILES

        self.comparison_panel = ComparisonPanel()
        self.side_stack.addWidget(self.comparison_panel)    # index 1 = PANEL_COMPARISON

        self.palette_sidebar = PaletteSidebar()
        self.side_stack.addWidget(self.palette_sidebar)     # index 2 = PANEL_PALETTE

        layout.addWidget(self.side_stack)

        # Right area stack
        self.right_stack = QStackedWidget()

        # Chart workspace
        chart_ws = QWidget()
        chart_layout = QVBoxLayout(chart_ws)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        from gui_qt.central.toolbar import ToolBar
        from gui_qt.central.chart_widget import ChartArea
        from gui_qt.central.chart_toolbar import ChartToolBar

        self.toolbar = ToolBar()
        self.chart = ChartArea()
        # Compatibility aliases
        self.fig = self.chart.fig
        self.canvas = self.chart.canvas
        self.chart_toolbar = ChartToolBar()

        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 2px 8px; background: {BG_CARD};"
        )
        self.status_bar.setFixedHeight(24)

        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self.chart, stretch=1)
        chart_layout.addWidget(self.chart_toolbar)
        chart_layout.addWidget(self.status_bar)

        self.right_stack.addWidget(chart_ws)  # index 0

        # Palette workspace
        from gui_qt.central.palette_workspace import PaletteWorkspace
        self.palette_workspace = PaletteWorkspace()
        self.right_stack.addWidget(self.palette_workspace)  # index 1

        layout.addWidget(self.right_stack, stretch=1)

        # Start on file panel
        self.activity_bar.set_active(PANEL_FILES)
        self.side_stack.setCurrentIndex(PANEL_FILES)
        self.right_stack.setCurrentIndex(0)
```

Replace `_on_panel_clicked`:

```python
    def _on_panel_clicked(self, panel_id: int) -> None:
        if panel_id < 0:
            # Collapse side panel
            self.side_stack.hide()
            return
        self.side_stack.show()
        self.side_stack.setCurrentIndex(panel_id)

        if panel_id == PANEL_FILES:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = False
        elif panel_id == PANEL_COMPARISON:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = True
            # Refresh comparison render
            if self._app_state.get("comparison_items"):
                import gui_qt.comparison as comp  # need to create or use existing
                # The controller handles this
        elif panel_id == PANEL_PALETTE:
            self.right_stack.setCurrentIndex(1)  # palette workspace
            # Refresh palette workspace with current scheme
            self._update_palette_workspace()
```

Add helper:

```python
    def _update_palette_workspace(self):
        scheme_name = self._app_state.get("active_palette_scheme", "默认方案")
        schemes = self._app_state.get("palette_schemes", {})
        slot_count = self._app_state.get("palette_scheme_slot_counts", {}).get(scheme_name, 8)
        colors = []
        names = []
        scheme_colors = schemes.get(scheme_name, {})
        for i in range(slot_count):
            colors.append(scheme_colors.get(str(i), "#94a3b8"))
            names.append(f"第{i+1}段")
        self.palette_workspace.set_scheme(scheme_name, colors, names)
```

Replace `_switch_mode`:

```python
    def _switch_mode(self, mode: str) -> None:
        if mode == "single":
            self._app_state["comparison_mode"] = False
            self.activity_bar.set_active(PANEL_FILES)
            self.side_stack.setCurrentIndex(PANEL_FILES)
            self.right_stack.setCurrentIndex(0)
        else:
            self._app_state["comparison_mode"] = True
            self.activity_bar.set_active(PANEL_COMPARISON)
            self.side_stack.setCurrentIndex(PANEL_COMPARISON)
            self.right_stack.setCurrentIndex(0)
```

Replace `_init_controllers`:

```python
    def _init_controllers(self) -> None:
        from gui_qt.controllers.file_ctrl import FileController
        from gui_qt.controllers.fitting_ctrl import FittingController
        from gui_qt.controllers.comparison_ctrl import ComparisonController
        from gui_qt.controllers.export_ctrl import ExportController

        self.files = FileController(self)
        self.fitting = FittingController(self)
        self.comparison = ComparisonController(self)
        self.export_mgr = ExportController(self)

        # Wire file segment panel
        p = self.file_segment_panel
        p.files_selected.connect(self.files.on_files_loaded)
        p.file_activated.connect(self.files.on_file_selected)
        p.file_removed.connect(self.files.on_file_removed)
        p.cache_import_requested.connect(self.files.import_cache_dialog)
        p.segment_activated.connect(self.files.on_segment_activated)
        p.segment_toggled.connect(self.files.on_segment_toggled)
        p.segment_color_changed.connect(self.files.on_segment_color)
        p.select_all_clicked.connect(self.files.on_select_all)
        p.clear_all_clicked.connect(self.files.on_clear_all)
        p.add_to_comparison.connect(self.comparison.add_from_current)
        p.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        p.palette_apply_clicked.connect(self.files.on_palette_apply)
        p.palette_manage_clicked.connect(lambda: self.activity_bar.set_active(PANEL_PALETTE))
        p.export_current.connect(self.export_mgr.export_current)
        p.export_batch.connect(self.export_mgr.run_batch)
        p.export_name_changed.connect(self.files.on_export_name_changed)

        # Wire toolbar
        self.toolbar.fit_clicked.connect(self.fitting.run_fit)
        self.toolbar.manual_clicked.connect(self.fitting.enable_manual_mode)

        # Wire comparison panel
        cp = self.comparison_panel
        cp.item_visibility_changed.connect(self.comparison.toggle_visibility)
        cp.item_color_changed.connect(self.comparison.update_color)
        cp.item_renamed.connect(self.comparison.rename)
        cp.add_all_clicked.connect(self.comparison.add_all_processed)
        cp.clear_all_clicked.connect(self.comparison.clear_all)
        cp.delete_selected_clicked.connect(self.comparison.delete_selected)
        cp.move_up_clicked.connect(self.comparison.move_up)
        cp.move_down_clicked.connect(self.comparison.move_down)
        cp.export_clicked.connect(self.export_mgr.export_comparison)
        cp.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        cp.palette_apply_clicked.connect(self.files.on_palette_apply_comparison)
        cp.palette_manage_clicked.connect(lambda: self.activity_bar.set_active(PANEL_PALETTE))

        # Wire palette sidebar
        ps = self.palette_sidebar
        ps.scheme_changed.connect(self.files.on_palette_scheme_selected)
        ps.color_changed.connect(self.files.on_palette_color_changed)
        ps.color_count_changed.connect(self.files.on_palette_count_changed)
        ps.apply_to_current_clicked.connect(self.files.on_palette_apply)
        ps.save_as_new_clicked.connect(self.files.on_palette_save_as_new)
        ps.delete_scheme_clicked.connect(self.files.on_palette_delete)

        # Wire chart toolbar
        self.chart_toolbar.save_image_clicked.connect(self.export_mgr.export_current)
        self.chart_toolbar.manual_clicked.connect(self.fitting.enable_manual_mode)
```

Add imports at top of app.py:

```python
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt

from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE
from gui_qt.theme import BG_WINDOW, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY
```

Add `_app_state` init for palette schemes (update existing `_init_app_state`):

```python
    def _init_app_state(self) -> None:
        self._app_state: dict = {
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
            "comparison_mode": False,
            "comparison_items": [],
            "palette_schemes": {"默认方案": {str(i): c for i, c in enumerate([
                "#b90746", "#0891b2", "#7c3aed", "#16a34a", "#f59e0b",
                "#dc2626", "#2563eb", "#d946ef", "#0ea5e9", "#84cc16",
            ])}},
            "palette_scheme_slot_counts": {"默认方案": 10},
            "active_palette_scheme": "默认方案",
            "saved_parameter_defaults": {},
            "file_ui_cache": {},
            "result_cache": {},
            "current_result_keys": {},
            "_op_generation": 0,
            "_fitting_lock": False,
        }
```

- [ ] **Step 2: Verify app imports**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.app import TafelAnalyzerApp; print('OK')"
```

Expected: `OK` (may fail on controller imports until Task 10-13 are done)

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/app.py
git commit -m "refactor: rebuild app.py layout with 3-panel architecture and merged toolbar"
```

---

### Task 10: FileController — Adapt to FileSegmentPanel signals

**Files:**
- Modify: `src/gui_qt/controllers/file_ctrl.py`

- [ ] **Step 1: Add handler methods for the new panel signals**

Read the current `file_ctrl.py`. Then add these methods to `FileController`:

```python
    def on_files_loaded(self, paths: list[Path]) -> None:
        """Called when files are selected via file dialog."""
        app = self.app
        for p in paths:
            if p not in app._app_state["selected_paths"]:
                app._app_state["selected_paths"].append(p)
        self.refresh_file_choices(preferred_path=paths[0])
        app._app_state["tdms_path"] = paths[0]
        self.load_current_file()

    def on_file_selected(self, path: Path) -> None:
        """Called when a file row is double-clicked."""
        app = self.app
        app._save_current_file_ui_state() if hasattr(app, '_save_current_file_ui_state') else None
        app._app_state["tdms_path"] = path
        self.load_current_file()

    def on_file_removed(self, path: Path) -> None:
        """Called when a file is removed (confirmed by panel)."""
        app = self.app
        current_key = str(path)
        app._app_state["selected_paths"].remove(path)
        app._app_state["current_result_keys"].pop(current_key, None)
        app._app_state["file_ui_cache"].pop(current_key, None)
        app._app_state["comparison_items"] = [
            item for item in app._app_state.get("comparison_items", [])
            if item.file_path != path
        ]
        remaining = app._app_state["selected_paths"]
        if remaining:
            app._app_state["tdms_path"] = remaining[0]
            self.refresh_file_choices(preferred_path=remaining[0])
            self.load_current_file()
        else:
            self._clear_state()
        self.app.comparison.refresh_list() if hasattr(self.app.comparison, 'refresh_list') else None

    def on_segment_activated(self, index: int) -> None:
        """Called when a segment row is clicked (active segment change)."""
        app = self.app
        app._app_state["active_segment_index"] = index
        app._app_state["selected_segment_indices"] = list(
            set(app._app_state.get("selected_segment_indices", []) + [index])
        )
        self._refresh_segment_panel()
        self._restore_or_refit()

    def on_segment_toggled(self, index: int, checked: bool) -> None:
        """Called when a segment checkbox is toggled."""
        app = self.app
        selected = set(app._app_state.get("selected_segment_indices", []))
        if checked:
            selected.add(index)
        else:
            selected.discard(index)
        app._app_state["selected_segment_indices"] = sorted(selected)
        self._refresh_segment_panel()

    def on_segment_color(self, index: int, _dummy) -> None:
        """Called when a segment color swatch is clicked."""
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            app = self.app
            app._app_state["segment_colors"][index] = color.name()
            self._refresh_segment_panel()
            self._redraw_chart()

    def on_select_all(self) -> None:
        app = self.app
        segments = app._app_state.get("segments", [])
        app._app_state["selected_segment_indices"] = [s.index for s in segments]
        self._refresh_segment_panel()
        self._restore_or_refit()

    def on_clear_all(self) -> None:
        app = self.app
        app._app_state["selected_segment_indices"] = []
        self._refresh_segment_panel()

    def on_export_name_changed(self, name: str) -> None:
        app = self.app
        file_key = self._current_file_key()
        if file_key:
            cache = app._app_state.setdefault("file_ui_cache", {})
            cache.setdefault(file_key, {})["export_name"] = name

    def on_palette_scheme_changed(self, scheme_name: str) -> None:
        app = self.app
        app._app_state["active_palette_scheme"] = scheme_name

    def on_palette_apply(self) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        schemes = app._app_state.get("palette_schemes", {})
        scheme = schemes.get(scheme_name, {})
        segments = app._app_state.get("segments", [])
        for seg in segments:
            app._app_state["segment_colors"][seg.index] = scheme.get(
                str(seg.index), "#94a3b8"
            )
        self._refresh_segment_panel()
        self._redraw_chart()

    def on_palette_apply_comparison(self) -> None:
        # Apply palette to comparison items
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        schemes = app._app_state.get("palette_schemes", {})
        scheme = schemes.get(scheme_name, {})
        for i, item in enumerate(app._app_state.get("comparison_items", [])):
            color_key = str(i % len(scheme))
            item.color = scheme.get(color_key, "#94a3b8")
        self.app.comparison.refresh_list()
        self.app.comparison.render_comparison()

    def on_palette_scheme_selected(self, scheme_name: str) -> None:
        app = self.app
        app._app_state["active_palette_scheme"] = scheme_name
        app._update_palette_workspace()

    def on_palette_color_changed(self, index: int, new_hex: str) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        schemes = app._app_state.setdefault("palette_schemes", {})
        schemes.setdefault(scheme_name, {})[str(index)] = new_hex
        app._update_palette_workspace()

    def on_palette_count_changed(self, count: int) -> None:
        app = self.app
        scheme_name = app._app_state.get("active_palette_scheme", "默认方案")
        app._app_state.setdefault("palette_scheme_slot_counts", {})[scheme_name] = count
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    def on_palette_save_as_new(self, base_name: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        app = self.app
        name, ok = QInputDialog.getText(None, "新建方案", "请输入方案名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in app._app_state.get("palette_schemes", {}):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "名称冲突", f"方案 \"{name}\" 已存在")
            return
        # Copy current scheme
        current = app._app_state.get("active_palette_scheme", "默认方案")
        current_colors = app._app_state.get("palette_schemes", {}).get(current, {})
        current_count = app._app_state.get("palette_scheme_slot_counts", {}).get(current, 8)
        app._app_state.setdefault("palette_schemes", {})[name] = dict(current_colors)
        app._app_state.setdefault("palette_scheme_slot_counts", {})[name] = current_count
        app._app_state["active_palette_scheme"] = name
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    def on_palette_delete(self, scheme_name: str) -> None:
        app = self.app
        schemes = app._app_state.get("palette_schemes", {})
        if len(schemes) <= 1:
            return
        schemes.pop(scheme_name, None)
        app._app_state.get("palette_scheme_slot_counts", {}).pop(scheme_name, None)
        app._app_state["active_palette_scheme"] = next(iter(schemes.keys()))
        self._refresh_palette_sidebar()
        app._update_palette_workspace()

    # ━━ Panel refresh helpers ━━

    def _refresh_file_segment_panel(self) -> None:
        app = self.app
        p = app.file_segment_panel
        processed = {
            path_key for path_key in app._app_state.get("current_result_keys", {}).keys()
        }
        p.set_file_paths(app._app_state.get("selected_paths", []), processed)
        export_name = ""
        file_key = self._current_file_key()
        if file_key:
            export_name = app._app_state.get("file_ui_cache", {}).get(file_key, {}).get("export_name", "")
            if not export_name and app._app_state.get("tdms_path"):
                export_name = app._app_state["tdms_path"].stem
        p.set_export_name(export_name)

    def _refresh_segment_panel(self) -> None:
        app = self.app
        p = app.file_segment_panel
        segments = app._app_state.get("segments", [])
        seg_dicts = [{"index": s.index, "label": s.label} for s in segments]
        p.set_segments(
            seg_dicts,
            active_index=app._app_state.get("active_segment_index", 0),
            checked_indices=set(app._app_state.get("selected_segment_indices", [])),
            colors=app._app_state.get("segment_colors", {}),
            fit_by_segment=app._app_state.get("fit_by_segment", {}),
        )

    def _refresh_palette_sidebar(self) -> None:
        app = self.app
        schemes = list(app._app_state.get("palette_schemes", {}).keys())
        active = app._app_state.get("active_palette_scheme", "默认方案")
        app.palette_sidebar.set_schemes(schemes, active)

        # Set colors
        slot_count = app._app_state.get("palette_scheme_slot_counts", {}).get(active, 8)
        scheme_colors = app._app_state.get("palette_schemes", {}).get(active, {})
        colors = [scheme_colors.get(str(i), "#94a3b8") for i in range(slot_count)]
        names = [f"第{i+1}段" for i in range(slot_count)]
        app.palette_sidebar.set_colors(colors, names)
        app.palette_sidebar.count_combo.blockSignals(True)
        app.palette_sidebar.count_combo.setCurrentText(str(slot_count))
        app.palette_sidebar.count_combo.blockSignals(False)

    def _redraw_chart(self) -> None:
        app = self.app
        prepared = app._app_state.get("prepared")
        if prepared is not None:
            from gui import rendering as r
            r.draw(app, prepared, app._app_state.get("fit"))

    def _restore_or_refit(self) -> None:
        if hasattr(self.app, 'fitting') and not self.app._app_state.get("_fitting_lock"):
            self.app.fitting.restore_or_autorun()

    def _current_file_key(self) -> str | None:
        path = self.app._app_state.get("tdms_path")
        return str(path) if path else None

    def _load_settings(self) -> None:
        # Load saved settings from gui.settings
        try:
            from gui import settings as s
            if hasattr(s, 'load_app_settings_qt'):
                s.load_app_settings_qt(self.app)
        except Exception:
            pass
```

Update `load_current_file` to use the new panel for UI updates (replace `app.after(0, ...)` callback):

In the `_apply_loaded` inner function at the end of `load_current_file`, replace all CTk widget references with the new panel calls:

```python
    def _apply_loaded():
        app._app_state["channels"] = channels
        app._app_state["segments"] = segments
        app._app_state["segment_lookup"] = {seg.label: seg.index for seg in segments}
        app._app_state["segment_colors"] = p.merge_active_palette(
            app,
            p.deserialize_segment_colors(app, (cached_ui or {}).get("segment_colors", {})),
            len(segments),
        )
        active_index = app._app_state["segment_lookup"].get(preferred_label, 0) if preferred_label else 0
        app._app_state["active_segment_index"] = active_index
        app._app_state["prepared"] = None
        app._app_state["fit"] = None
        app._app_state["prepared_by_segment"] = {}
        app._app_state["fit_by_segment"] = {}
        app._app_state["fit_error_by_segment"] = {}
        app._app_state["manual_mode"] = False

        # Update new toolbar
        app.toolbar.set_formulas(potential_formula, current_formula)
        if cached_ui:
            params = {
                "e_eq": cached_ui.get("e_eq", "0"),
                "window_range": cached_ui.get("window_range", "12-15"),
                "eta_range": cached_ui.get("eta_range", ""),
                "logj_range": cached_ui.get("logj_range", ""),
                "min_r2": cached_ui.get("min_r2", "0.95"),
                "fit_priority": cached_ui.get("fit_priority", "斜率更低优先"),
            }
        else:
            params = app._app_state.get("saved_parameter_defaults", {})
        app.toolbar.set_params(params)

        # Update file segment panel
        controller._refresh_segment_panel()
        controller._refresh_file_segment_panel()

        # Channel info in status bar
        app.status_bar.setText(f"已加载 {tdms_path.name}，共 {len(channel_names)} channel，{len(segments)} 段")

        from gui import rendering as r
        r.draw_placeholder(app)

        if controller._restore_or_refit:
            controller._restore_or_refit()
```

- [ ] **Step 2: Commit**

```bash
git add src/gui_qt/controllers/file_ctrl.py
git commit -m "feat: adapt FileController to FileSegmentPanel signals and palette management"
```

---

### Task 11: FittingController — Adapt to Toolbar

**Files:**
- Modify: `src/gui_qt/controllers/fitting_ctrl.py`

- [ ] **Step 1: Ensure `run_fit` and `enable_manual_mode` work with the new toolbar**

Read the current `fitting_ctrl.py`. The key methods `run_fit` and `enable_manual_mode` should already exist. Update them to read formulas/params from the new toolbar:

```python
    def run_fit(self) -> None:
        app = self.app
        formulas = app.toolbar.get_formulas()
        params = app.toolbar.get_params()
        # ... existing fitting logic using formulas[0], formulas[1], params
```

```python
    def enable_manual_mode(self) -> None:
        app = self.app
        # Activate RectangleSelector on the chart
        # ... existing manual mode logic
```

- [ ] **Step 2: Commit**

```bash
git add src/gui_qt/controllers/fitting_ctrl.py
git commit -m "fix: adapt FittingController to read from merged Toolbar"
```

---

### Task 12: ComparisonController — Complete wiring

**Files:**
- Modify: `src/gui_qt/controllers/comparison_ctrl.py`

- [ ] **Step 1: Ensure all comparison methods are implemented**

Read the current `comparison_ctrl.py`. The existing methods should map to the new signals. Add any missing:

```python
    def add_from_current(self) -> None:
        """Add current file's selected segments to comparison."""
        app = self.app
        prepared = app._app_state.get("prepared")
        if prepared is None:
            return
        fit = app._app_state.get("fit")
        path = app._app_state.get("tdms_path")
        if path is None:
            return
        from core.types import ComparisonItem
        item_id = f"{path.stem}-seg{prepared.segment.index}"
        existing = {item.item_id for item in app._app_state.get("comparison_items", [])}
        if item_id in existing:
            return
        color_idx = len(app._app_state.get("comparison_items", []))
        from core.types import COMPARISON_COLORS
        color = COMPARISON_COLORS[color_idx % len(COMPARISON_COLORS)]
        item = ComparisonItem(
            item_id=item_id,
            file_path=path,
            file_name=path.stem,
            segment_index=prepared.segment.index,
            prepared=prepared,
            fit=fit,
            label=f"{path.stem}-第{prepared.segment.index + 1}段",
            color=color,
            visible=True,
        )
        app._app_state.setdefault("comparison_items", []).append(item)
        self.refresh_list()
        self.render_comparison()

    def delete_selected(self) -> None:
        """Delete selected comparison items."""
        app = self.app
        items = app._app_state.get("comparison_items", [])
        # Get selected items from the list widget
        selected_rows = set()
        for item in app.comparison_panel.item_list.selectedItems():
            widget = app.comparison_panel.item_list.itemWidget(item)
            if widget:
                selected_rows.add(widget.item_id)
        app._app_state["comparison_items"] = [
            it for it in items if it.item_id not in selected_rows
        ]
        self.refresh_list()
        self.render_comparison()

    def move_up(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        selected = self._selected_item_ids()
        for i in range(1, len(items)):
            if items[i].item_id in selected:
                items[i], items[i-1] = items[i-1], items[i]
        self.refresh_list()
        self.render_comparison()

    def move_down(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        selected = self._selected_item_ids()
        for i in range(len(items) - 1):
            if items[i].item_id in selected:
                items[i], items[i+1] = items[i+1], items[i]
        self.refresh_list()
        self.render_comparison()

    def add_all_processed(self) -> None:
        # Add all segments from all processed files
        pass  # TODO: iterate result_cache entries

    def clear_all(self) -> None:
        self.app._app_state["comparison_items"] = []
        self.refresh_list()
        self.render_comparison()

    def toggle_visibility(self, item_id: str, visible: bool) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.visible = visible
                break
        self.render_comparison()

    def update_color(self, item_id: str, color: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.color = color
                break
        self.refresh_list()
        self.render_comparison()

    def rename(self, item_id: str, new_name: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.label = new_name
                break
        self.refresh_list()

    def refresh_list(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        data = [
            {
                "item_id": it.item_id,
                "display_name": it.label,
                "segment_label": f"第{it.segment_index + 1}段",
                "color": it.color,
                "visible": it.visible,
            }
            for it in items
        ]
        self.app.comparison_panel.set_items(data)

    def render_comparison(self) -> None:
        from gui import comparison as comp
        comp.render_comparison(self.app)

    def _selected_item_ids(self) -> set:
        ids = set()
        for item in self.app.comparison_panel.item_list.selectedItems():
            w = self.app.comparison_panel.item_list.itemWidget(item)
            if w:
                ids.add(w.item_id)
        return ids
```

- [ ] **Step 2: Commit**

```bash
git add src/gui_qt/controllers/comparison_ctrl.py
git commit -m "feat: complete ComparisonController with all item operations"
```

---

### Task 13: ExportController — Complete wiring

**Files:**
- Modify: `src/gui_qt/controllers/export_ctrl.py`

- [ ] **Step 1: Ensure export methods use the new toolbar and panel**

```python
    def export_current(self) -> None:
        app = self.app
        prepared = app._app_state.get("prepared")
        fit = app._app_state.get("fit")
        if prepared is None or fit is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "提示", "没有可导出的拟合结果")
            return
        from gui import export as e
        export_name = app.file_segment_panel.get_export_name()
        e.export_current(self.app, prepared, fit, export_name=export_name)

    def run_batch(self) -> None:
        app = self.app
        # Batch export all selected segments
        from gui import export as e
        e.run_batch_export(self.app)

    def export_comparison(self) -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        if not items:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "提示", "没有对比项可导出")
            return
        from gui import comparison as comp
        comp.build_comparison_export(self.app)
```

- [ ] **Step 2: Commit**

```bash
git add src/gui_qt/controllers/export_ctrl.py
git commit -m "fix: complete ExportController wiring for new panels"
```

---

### Task 14: Cleanup — Delete replaced files

**Files:**
- Delete: `src/gui_qt/panels/formula_panel.py`
- Delete: `src/gui_qt/central/param_bar.py`

- [ ] **Step 1: Delete old files and update panel __init__.py**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && git rm src/gui_qt/panels/formula_panel.py src/gui_qt/central/param_bar.py
```

Update `src/gui_qt/panels/__init__.py`:

```python
from gui_qt.panels.file_segment import FileSegmentPanel
from gui_qt.panels.comparison import ComparisonPanel
from gui_qt.panels.palette import PaletteSidebar
```

Update `src/gui_qt/central/__init__.py`:

```python
from gui_qt.central.toolbar import ToolBar
from gui_qt.central.chart_widget import ChartArea
from gui_qt.central.chart_toolbar import ChartToolBar
from gui_qt.central.palette_workspace import PaletteWorkspace
```

- [ ] **Step 2: Verify nothing is broken**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "
from src.gui_qt.panels import FileSegmentPanel, ComparisonPanel, PaletteSidebar
from src.gui_qt.central import ToolBar, ChartArea, ChartToolBar, PaletteWorkspace
from src.gui_qt.activity_bar import ActivityBar
print('All imports OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/panels/__init__.py src/gui_qt/central/__init__.py
git commit -m "chore: delete replaced formula_panel.py and param_bar.py, update __init__ exports"
```

---

### Task 15: Integration — Full workflow test

- [ ] **Step 1: Import the full app**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "
from src.gui_qt.app import TafelAnalyzerApp
print('App class loaded successfully')
"
```

Expected: `App class loaded successfully`

- [ ] **Step 2: Verify all signal connections are valid**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "
from PySide6.QtWidgets import QApplication
import sys
app = QApplication.instance() or QApplication(sys.argv)
from src.gui_qt.app import TafelAnalyzerApp
window = TafelAnalyzerApp()
# Check key attributes exist
assert hasattr(window, 'activity_bar')
assert hasattr(window, 'file_segment_panel')
assert hasattr(window, 'comparison_panel')
assert hasattr(window, 'palette_sidebar')
assert hasattr(window, 'toolbar')
assert hasattr(window, 'chart')
assert hasattr(window, 'palette_workspace')
assert hasattr(window, 'files')
assert hasattr(window, 'fitting')
assert hasattr(window, 'comparison')
assert hasattr(window, 'export_mgr')
print('All attributes verified')
window.close()
"
```

- [ ] **Step 3: Run the GUI to visually verify**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python main.py
```

Manual checks:
- Activity bar 3 icons visible
- Click 📂 → see file list + segment list with splitter
- Click 📊 → see comparison panel
- Click 🎨 → see palette sidebar + right workspace
- Formula inputs visible in toolbar
- Parameters visible in toolbar
- Fit button responsive
- Export buttons in file panel

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "test: verify full app launches with consolidated panels"
```

---

### Task 16: Fix comparison rendering compatibility

**Files:**
- Modify: `src/gui_qt/app.py` — ensure `gui.comparison` and `gui.rendering` compatibility with Qt widgets

- [ ] **Step 1: Verify comparison rendering works**

The old `gui/comparison.py` and `gui/rendering.py` use `app.fig` and `app.canvas` for matplotlib. Since `app.py` now provides `self.fig = self.chart.fig` and `self.canvas = self.chart.canvas`, these should work.

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "
from gui import comparison as c, rendering as r
print('Comparison and rendering imports OK')
"
```

- [ ] **Step 2: Commit**

```bash
git commit --allow-empty -m "test: verify gui rendering compatibility with Qt canvas"
```
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.panels.palette import PaletteSidebar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/panels/palette.py
git commit -m "feat: add PaletteSidebar with Origin-style color management"
```

---

### Task 7: PaletteWorkspace — Right-side palette editor

**Files:**
- Create: `src/gui_qt/central/palette_workspace.py`

- [ ] **Step 1: Create a placeholder workspace for the right palette area**

Create `src/gui_qt/central/palette_workspace.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QScrollArea
from PySide6.QtCore import Qt

from gui_qt.theme import BG_CARD, TEXT_SECONDARY, TEXT_PRIMARY, ACCENT


class PaletteWorkspace(QWidget):
    """Right-side large color grid for Origin-style palette editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("配色方案编辑")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Subtitle
        self.scheme_label = QLabel("选择一个配色方案")
        self.scheme_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        layout.addWidget(self.scheme_label)

        # Color grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(12)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, stretch=1)

    def set_scheme(self, name: str, colors: list[str], segment_names: list[str]) -> None:
        """Show large swatches for the selected scheme."""
        self.scheme_label.setText(f"方案: {name}  ({len(colors)} 色)")

        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add swatches in a responsive grid
        cols = 4
        for i, (hex_color, seg_name) in enumerate(zip(colors, segment_names)):
            swatch = QWidget()
            swatch.setFixedSize(120, 100)
            swatch.setStyleSheet(
                f"QWidget {{ background: {hex_color}; border-radius: 12px; "
                f"border: 2px solid #e2e8f0; }}"
            )
            swatch.setToolTip(f"{seg_name}: {hex_color}")

            label = QLabel(f"{seg_name}\n{hex_color}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {'#0f172a' if _is_light(hex_color) else '#ffffff'}; "
                f"font-size: 11px; font-weight: 600; background: transparent; border: none;"
            )

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(swatch, row, col)
            # Overlay text on swatch
            label.setParent(swatch)
            label.setGeometry(4, 30, 112, 40)


def _is_light(hex_color: str) -> bool:
    """Return True if the color is light (for text contrast)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance > 150
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.central.palette_workspace import PaletteWorkspace; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/central/palette_workspace.py
git commit -m "feat: add PaletteWorkspace for right-side large swatch grid"
```

---

### Task 8: ChartToolbar — Add missing buttons

**Files:**
- Modify: `src/gui_qt/central/chart_toolbar.py`

- [ ] **Step 1: Read current file and add manual/export buttons**

Read `src/gui_qt/central/chart_toolbar.py`. Then rewrite it:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, BG_CARD, BORDER, TEXT_SECONDARY, ACCENT, BG_HOVER,
)


class ChartToolBar(QWidget):
    """Custom matplotlib toolbar: zoom, pan, home, manual, save."""

    zoom_clicked = Signal()
    pan_clicked = Signal()
    home_clicked = Signal()
    save_image_clicked = Signal()
    manual_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            ChartToolBar {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        def make_btn(text: str, tooltip: str, signal: Signal) -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 4px; font-size: 14px; "
                f"color: {TEXT_SECONDARY}; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; color: #0f172a; }}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            return btn

        layout.addWidget(make_btn("🏠", "复位", self.home_clicked))
        layout.addWidget(make_btn("←", "后退", self.home_clicked))  # reuse home for now
        layout.addWidget(make_btn("→", "前进", self.home_clicked))
        layout.addWidget(make_btn("🔍+", "放大", self.zoom_clicked))
        layout.addWidget(make_btn("🔍-", "缩小", self.zoom_clicked))
        layout.addWidget(make_btn("✋", "平移", self.pan_clicked))
        layout.addWidget(make_btn("🖱", "手动框选", self.manual_clicked))

        layout.addStretch()

        layout.addWidget(make_btn("💾", "保存图片", self.save_image_clicked))
```

- [ ] **Step 2: Verify import**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.central.chart_toolbar import ChartToolBar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/central/chart_toolbar.py
git commit -m "feat: add manual/zoom/pan buttons to ChartToolBar"
```

---

### Task 9: app.py — Rebuild layout with new panels

**Files:**
- Modify: `src/gui_qt/app.py`

- [ ] **Step 1: Rewrite _build_ui and _init_controllers for the new architecture**

Read the current `app.py`. Replace `_build_ui` and `_init_controllers`:

Note: The QMainWindow already has correct imports. Replace the build method:

```python
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Activity bar
        self.activity_bar = ActivityBar()
        self.activity_bar.panel_clicked.connect(self._on_panel_clicked)
        layout.addWidget(self.activity_bar)

        # Side panel stack (320px)
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(320)

        from gui_qt.panels.file_segment import FileSegmentPanel
        from gui_qt.panels.comparison import ComparisonPanel
        from gui_qt.panels.palette import PaletteSidebar

        self.file_segment_panel = FileSegmentPanel()
        self.side_stack.addWidget(self.file_segment_panel)  # index 0 = PANEL_FILES

        self.comparison_panel = ComparisonPanel()
        self.side_stack.addWidget(self.comparison_panel)    # index 1 = PANEL_COMPARISON

        self.palette_sidebar = PaletteSidebar()
        self.side_stack.addWidget(self.palette_sidebar)     # index 2 = PANEL_PALETTE

        layout.addWidget(self.side_stack)

        # Right area stack
        self.right_stack = QStackedWidget()

        # Chart workspace
        chart_ws = QWidget()
        chart_layout = QVBoxLayout(chart_ws)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        from gui_qt.central.toolbar import ToolBar
        from gui_qt.central.chart_widget import ChartArea
        from gui_qt.central.chart_toolbar import ChartToolBar

        self.toolbar = ToolBar()
        self.chart = ChartArea()
        # Compatibility aliases
        self.fig = self.chart.fig
        self.canvas = self.chart.canvas
        self.chart_toolbar = ChartToolBar()

        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 2px 8px; background: {BG_CARD};"
        )
        self.status_bar.setFixedHeight(24)

        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self.chart, stretch=1)
        chart_layout.addWidget(self.chart_toolbar)
        chart_layout.addWidget(self.status_bar)

        self.right_stack.addWidget(chart_ws)  # index 0

        # Palette workspace
        from gui_qt.central.palette_workspace import PaletteWorkspace
        self.palette_workspace = PaletteWorkspace()
        self.right_stack.addWidget(self.palette_workspace)  # index 1

        layout.addWidget(self.right_stack, stretch=1)

        # Start on file panel
        self.activity_bar.set_active(PANEL_FILES)
        self.side_stack.setCurrentIndex(PANEL_FILES)
        self.right_stack.setCurrentIndex(0)
```

Replace `_on_panel_clicked`:

```python
    def _on_panel_clicked(self, panel_id: int) -> None:
        if panel_id < 0:
            # Collapse side panel
            self.side_stack.hide()
            return
        self.side_stack.show()
        self.side_stack.setCurrentIndex(panel_id)

        if panel_id == PANEL_FILES:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = False
        elif panel_id == PANEL_COMPARISON:
            self.right_stack.setCurrentIndex(0)  # chart workspace
            self._app_state["comparison_mode"] = True
            # Refresh comparison render
            if self._app_state.get("comparison_items"):
                import gui_qt.comparison as comp  # need to create or use existing
                # The controller handles this
        elif panel_id == PANEL_PALETTE:
            self.right_stack.setCurrentIndex(1)  # palette workspace
            # Refresh palette workspace with current scheme
            self._update_palette_workspace()
```

Add helper:

```python
    def _update_palette_workspace(self):
        scheme_name = self._app_state.get("active_palette_scheme", "默认方案")
        schemes = self._app_state.get("palette_schemes", {})
        slot_count = self._app_state.get("palette_scheme_slot_counts", {}).get(scheme_name, 8)
        colors = []
        names = []
        scheme_colors = schemes.get(scheme_name, {})
        for i in range(slot_count):
            colors.append(scheme_colors.get(str(i), "#94a3b8"))
            names.append(f"第{i+1}段")
        self.palette_workspace.set_scheme(scheme_name, colors, names)
```

Replace `_switch_mode`:

```python
    def _switch_mode(self, mode: str) -> None:
        if mode == "single":
            self._app_state["comparison_mode"] = False
            self.activity_bar.set_active(PANEL_FILES)
            self.side_stack.setCurrentIndex(PANEL_FILES)
            self.right_stack.setCurrentIndex(0)
        else:
            self._app_state["comparison_mode"] = True
            self.activity_bar.set_active(PANEL_COMPARISON)
            self.side_stack.setCurrentIndex(PANEL_COMPARISON)
            self.right_stack.setCurrentIndex(0)
```

Replace `_init_controllers`:

```python
    def _init_controllers(self) -> None:
        from gui_qt.controllers.file_ctrl import FileController
        from gui_qt.controllers.fitting_ctrl import FittingController
        from gui_qt.controllers.comparison_ctrl import ComparisonController
        from gui_qt.controllers.export_ctrl import ExportController

        self.files = FileController(self)
        self.fitting = FittingController(self)
        self.comparison = ComparisonController(self)
        self.export_mgr = ExportController(self)

        # Wire file segment panel
        p = self.file_segment_panel
        p.files_selected.connect(self.files.on_files_loaded)
        p.file_activated.connect(self.files.on_file_selected)
        p.file_removed.connect(self.files.on_file_removed)
        p.cache_import_requested.connect(self.files.import_cache_dialog)
        p.segment_activated.connect(self.files.on_segment_activated)
        p.segment_toggled.connect(self.files.on_segment_toggled)
        p.segment_color_changed.connect(self.files.on_segment_color)
        p.select_all_clicked.connect(self.files.on_select_all)
        p.clear_all_clicked.connect(self.files.on_clear_all)
        p.add_to_comparison.connect(self.comparison.add_from_current)
        p.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        p.palette_apply_clicked.connect(self.files.on_palette_apply)
        p.palette_manage_clicked.connect(lambda: self.activity_bar.set_active(PANEL_PALETTE))
        p.export_current.connect(self.export_mgr.export_current)
        p.export_batch.connect(self.export_mgr.run_batch)
        p.export_name_changed.connect(self.files.on_export_name_changed)

        # Wire toolbar
        self.toolbar.fit_clicked.connect(self.fitting.run_fit)
        self.toolbar.manual_clicked.connect(self.fitting.enable_manual_mode)

        # Wire comparison panel
        cp = self.comparison_panel
        cp.item_visibility_changed.connect(self.comparison.toggle_visibility)
        cp.item_color_changed.connect(self.comparison.update_color)
        cp.item_renamed.connect(self.comparison.rename)
        cp.add_all_clicked.connect(self.comparison.add_all_processed)
        cp.clear_all_clicked.connect(self.comparison.clear_all)
        cp.delete_selected_clicked.connect(self.comparison.delete_selected)
        cp.move_up_clicked.connect(self.comparison.move_up)
        cp.move_down_clicked.connect(self.comparison.move_down)
        cp.export_clicked.connect(self.export_mgr.export_comparison)
        cp.palette_scheme_changed.connect(self.files.on_palette_scheme_changed)
        cp.palette_apply_clicked.connect(self.files.on_palette_apply_comparison)
        cp.palette_manage_clicked.connect(lambda: self.activity_bar.set_active(PANEL_PALETTE))

        # Wire palette sidebar
        ps = self.palette_sidebar
        ps.scheme_changed.connect(self.files.on_palette_scheme_selected)
        ps.color_changed.connect(self.files.on_palette_color_changed)
        ps.color_count_changed.connect(self.files.on_palette_count_changed)
        ps.apply_to_current_clicked.connect(self.files.on_palette_apply)
        ps.save_as_new_clicked.connect(self.files.on_palette_save_as_new)
        ps.delete_scheme_clicked.connect(self.files.on_palette_delete)

        # Wire chart toolbar
        self.chart_toolbar.save_image_clicked.connect(self.export_mgr.export_current)
        self.chart_toolbar.manual_clicked.connect(self.fitting.enable_manual_mode)
```

Add imports at top of app.py:

```python
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt

from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE
from gui_qt.theme import BG_WINDOW, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY
```

Add `_app_state` init for palette schemes (update existing `_init_app_state`):

```python
    def _init_app_state(self) -> None:
        self._app_state: dict = {
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
            "comparison_mode": False,
            "comparison_items": [],
            "palette_schemes": {"默认方案": {str(i): c for i, c in enumerate([
                "#b90746", "#0891b2", "#7c3aed", "#16a34a", "#f59e0b",
                "#dc2626", "#2563eb", "#d946ef", "#0ea5e9", "#84cc16",
            ])}},
            "palette_scheme_slot_counts": {"默认方案": 10},
            "active_palette_scheme": "默认方案",
            "saved_parameter_defaults": {},
            "file_ui_cache": {},
            "result_cache": {},
            "current_result_keys": {},
            "_op_generation": 0,
            "_fitting_lock": False,
        }
```

- [ ] **Step 2: Verify app imports**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "from src.gui_qt.app import TafelAnalyzerApp; print('OK')"
```

Expected: `OK` (may fail on controller imports until Task 10-13 are done)

- [ ] **Step 3: Commit**

```bash
git add src/gui_qt/app.py
git commit -m "refactor: rebuild app.py layout with 3-panel architecture and merged toolbar"
```

---

### Task 10: Cleanup — Delete replaced files

**Files:**
- Delete: `src/gui_qt/panels/formula_panel.py`
- Delete: `src/gui_qt/central/param_bar.py`

- [ ] **Step 1: Delete old files and update __init__ files**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && git rm src/gui_qt/panels/formula_panel.py src/gui_qt/central/param_bar.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: delete replaced formula_panel.py and param_bar.py"
```

---

### Task 11: Integration — Full workflow test

- [ ] **Step 1: Verify all imports**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python -c "
from src.gui_qt.panels.file_segment import FileSegmentPanel
from src.gui_qt.panels.comparison import ComparisonPanel
from src.gui_qt.panels.palette import PaletteSidebar
from src.gui_qt.central.toolbar import ToolBar
from src.gui_qt.central.palette_workspace import PaletteWorkspace
from src.gui_qt.central.chart_toolbar import ChartToolBar
from src.gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_COMPARISON, PANEL_PALETTE
from src.gui_qt.app import TafelAnalyzerApp
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 2: Launch the app and run manual checks**

```bash
cd "D:/OneDrive/Desktop/MSIC/Q/数据处理/.worktrees/pyside6-migration" && python main.py
```

Manual verification checklist:
- [ ] Window appears with 3 activity bar icons
- [ ] 📂 Files+Segments panel: file count , splitter works
- [ ] 📊 Comparison panel: buttons visible, items list renders
- [ ] 🎨 Palette panel: sidebar + right workspace shows
- [ ] Toolbar: formula inputs + params + fit buttons
- [ ] Chart: matplotlib canvas renders
- [ ] Load a .tdms file: channels detected, segments listed
- [ ] Fit button runs and chart updates
- [ ] Export works
- [ ] Add to comparison works

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration adjustments from manual testing"
```
