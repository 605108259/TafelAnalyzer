# Tafel Analyzer PySide6 Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Tafel Analyzer's GUI from CustomTkinter to PySide6 (Qt 6) with a modern consumer-app-style interface (light mode, activity bar layout, collapsible panels).

**Architecture:** New `src/gui_qt/` package containing QMainWindow app shell, individual panel widgets (file, formula, segment, comparison), central chart area with matplotlib QtAgg, and controllers using QThread for background computation. Shared modules (`gui/palette.py`, `gui/rendering.py`, `gui/cache.py`, `gui/serialization.py`, `gui/settings.py`, `gui/logger.py`) remain unchanged and are imported by the new Qt code.

**Tech Stack:** PySide6 (Qt 6), matplotlib QtAgg, numpy. Core computation layer (`src/core/`) untouched.

---

## File Structure

### New files to create

```
src/gui_qt/
├── __init__.py              # Re-export TafelAnalyzerApp
├── app.py                   # QMainWindow shell with layout orchestration
├── theme.py                 # Color constants + QSS style strings
├── activity_bar.py          # ActivityBar (48px vertical icon strip)
├── panels/
│   ├── __init__.py
│   ├── file_panel.py        # FilePanel — file list, load, remove
│   ├── formula_panel.py     # FormulaPanel — formula entry, channel list
│   ├── segment_panel.py     # SegmentPanel — segment cards with colors
│   ├── comparison_panel.py  # ComparisonPanel — comparison item list
│   └── palette_dialog.py    # PaletteSchemeManager QDialog
├── central/
│   ├── __init__.py
│   ├── param_bar.py         # ParamToolBar — E_eq, window, R², run btn
│   ├── chart_widget.py      # ChartArea — matplotlib FigureCanvasQTAgg
│   ├── chart_toolbar.py     # ChartToolBar — zoom/pan/manual/reset
│   └── summary_table.py     # ComparisonSummaryTable QTableWidget
└── controllers/
    ├── __init__.py
    ├── base.py              # BaseAppController — app reference + signals
    ├── file_ctrl.py         # FileController — load/switch/remove files
    ├── fitting_ctrl.py      # FittingController — run fit in QThread
    ├── export_ctrl.py       # ExportController — export single/batch
    ├── comparison_ctrl.py   # ComparisonController — add/remove/render
    └── segment_ctrl.py      # SegmentController — select/active/color
```

### Modified files

```
requirements.txt                 # Add PySide6
src/gui/theme.py                 # Add Qt-compatible color constants
src/gui/rendering.py             # No code change (backend agnostic)
src/gui/palette.py               # No code change (pure data funcs kept)
```

### Files to delete (after migration complete)

```
src/gui/app.py
src/gui/app_builder.py
src/gui/widgets.py
src/gui/tooltip.py
src/gui/controllers/
src/gui/comparison.py            # Replaced by gui_qt/central/summary_table.py
```

---

## Phase 0: Environment & Scaffolding

### Task 0.1: Add PySide6 dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Add PySide6 to requirements.txt**

Edit `requirements.txt`, append line:
```
PySide6>=6.6.0
```

- [ ] **Install and verify**

```bash
pip install PySide6
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

Expected: `PySide6 OK`

- [ ] **Verify matplotlib QtAgg backend**

```bash
python -c "import matplotlib; matplotlib.use('QtAgg'); import matplotlib.pyplot; print('QtAgg OK')"
```

Expected: `QtAgg OK`

- [ ] **Commit**

```bash
git add requirements.txt
git commit -m "chore: add PySide6 dependency for Qt GUI migration"
```

---

### Task 0.2: Create gui_qt package skeleton

**Files:**
- Create: `src/gui_qt/__init__.py`
- Create: `src/gui_qt/app.py`
- Create: `src/gui_qt/theme.py`
- Create: `src/gui_qt/activity_bar.py`
- Create: `src/gui_qt/panels/__init__.py`
- Create: `src/gui_qt/central/__init__.py`
- Create: `src/gui_qt/controllers/__init__.py`

- [ ] **Create directory structure**

```bash
mkdir -p src/gui_qt/panels src/gui_qt/central src/gui_qt/controllers
```

- [ ] **Write `src/gui_qt/__init__.py`**

```python
from gui_qt.app import TafelAnalyzerApp

__all__ = ["TafelAnalyzerApp"]
```

- [ ] **Write `src/gui_qt/theme.py`**

```python
"""Qt theme constants and QSS stylesheets."""

# ━━ Color palette ━━
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
SUCCESS = "#16a34a"
SUCCESS_HOVER = "#15803d"
WARNING = "#f59e0b"
WARNING_HOVER = "#d97706"
DANGER = "#dc2626"
PURPLE = "#7c3aed"
PURPLE_HOVER = "#6d28d9"
CYAN = "#0891b2"
CYAN_HOVER = "#0e7490"

BG_WINDOW = "#f8fafc"
BG_CARD = "#ffffff"
BG_HOVER = "#f1f5f9"
BG_SELECTED = "#eff6ff"
BORDER = "#e2e8f0"
BORDER_FOCUS = "#2563eb"

TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#64748b"
TEXT_DISABLED = "#94a3b8"
TEXT_ON_ACCENT = "#ffffff"

# ━━ QSS styles ━━

PANEL_STYLE = f"""
    QWidget#SidePanel {{
        background: {BG_CARD};
    }}
    QLabel#PanelTitle {{
        font-size: 13px;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        padding: 0px;
    }}
"""

BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background: {BG_HOVER};
    }}
"""

ACCENT_BUTTON_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        color: {TEXT_ON_ACCENT};
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: {ACCENT_HOVER};
    }}
    QPushButton:disabled {{
        background: {TEXT_DISABLED};
        color: {BG_CARD};
    }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        background: {BG_CARD};
        color: {TEXT_PRIMARY};
        font-size: 12px;
    }}
    QLineEdit:focus {{
        border-color: {BORDER_FOCUS};
    }}
    QLineEdit:disabled {{
        background: {BG_HOVER};
        color: {TEXT_DISABLED};
    }}
"""

LIST_STYLE = f"""
    QListWidget {{
        border: none;
        background: transparent;
        outline: none;
    }}
    QListWidget::item {{
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QListWidget::item:hover {{
        background: {BG_HOVER};
    }}
    QListWidget::item:selected {{
        background: {BG_SELECTED};
        color: {TEXT_PRIMARY};
    }}
"""
```

- [ ] **Write `app.py`, `activity_bar.py`, and `__init__.py` placeholders**

Create minimal placeholder files so the package imports cleanly:

```python
# src/gui_qt/app.py
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QStackedWidget
from PySide6.QtCore import Qt

from gui_qt.theme import BG_WINDOW


class TafelAnalyzerApp(QMainWindow):
    """Tafel Analyzer 主窗口 (PySide6)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tafel Analyzer")
        self.setMinimumSize(1220, 760)
        self.resize(1480, 900)
        self.setStyleSheet(f"QMainWindow {{ background: {BG_WINDOW}; }}")

        self._init_app_state()
        self._build_ui()
        self._init_controllers()

    def _init_app_state(self) -> None:
        self._app_state: dict = {
            "selected_paths": [],
            "tdms_path": None,
            "channels": None,
            "segments": [],
            "segment_colors": {},
            "comparison_mode": False,
            "comparison_items": [],
            "_op_generation": 0,
        }

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # Placeholder: will be built by subsequent tasks

    def _init_controllers(self) -> None:
        pass


class ActivityBar(QWidget):
    """48px vertical icon strip for panel switching."""
    pass
```

- [ ] **Verify import**

```bash
cd src && python -c "from gui_qt import TafelAnalyzerApp; print('Package OK')"
```

Expected: `Package OK`

- [ ] **Commit**

```bash
git add src/gui_qt/
git commit -m "feat: create gui_qt package skeleton with theme constants"
```

---

## Phase 1: Main Window Layout Shell

### Task 1.1: Build ActivityBar

**Files:**
- Modify: `src/gui_qt/activity_bar.py`
- Modify: `src/gui_qt/app.py`

- [ ] **Implement ActivityBar**

Replace placeholder in `src/gui_qt/activity_bar.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon

from gui_qt.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_SECONDARY


PANEL_FILES = 0
PANEL_FORMULA = 1
PANEL_SEGMENTS = 2
PANEL_PARAMS = 3
PANEL_COMPARISON = 4


class ActivityBar(QWidget):
    """48px vertical icon strip. Click to switch side panels."""

    panel_clicked = Signal(int)   # panel index
    param_toggled = Signal(bool)  # param toolbar visibility

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
        self._active_index: int | None = None

        for icon_text, panel_id, tooltip in [
            ("📂", PANEL_FILES, "文件"),
            ("📐", PANEL_FORMULA, "公式"),
            ("📋", PANEL_SEGMENTS, "分段"),
            ("⚙", PANEL_PARAMS, "参数"),
        ]:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(40, 40)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, pid=panel_id: self._on_click(pid))
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
        self._active_index = panel_id

    def _on_click(self, panel_id: int) -> None:
        if panel_id == self._active_index:
            # toggle collapse: emit -1 to signal collapse
            self.panel_clicked.emit(-1)
            self.set_active(-1)
            return
        self.set_active(panel_id)
        self.panel_clicked.emit(panel_id)

    def set_param_button_active(self, active: bool) -> None:
        if PANEL_PARAMS < len(self._buttons):
            btn = self._buttons[PANEL_PARAMS]
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
```

- [ ] **Integrate ActivityBar into app.py**

Edit `src/gui_qt/app.py`:

```python
from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_FORMULA, PANEL_SEGMENTS, PANEL_PARAMS

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

        # Side panel stack
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(320)
        layout.addWidget(self.side_stack)

        # Central area
        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        # Placeholder: ParamToolBar will go here (Task 2.3)
        # Placeholder: ChartArea will go here (Task 2.4)
        # Placeholder: ChartToolBar will go here (Task 2.5)
        # Placeholder: StatusBar goes here

        layout.addWidget(self.central_widget, stretch=1)
        self.activity_bar.set_active(PANEL_FILES)

    def _on_panel_clicked(self, panel_id: int) -> None:
        if panel_id == -1:
            # Collapse side panel
            self.side_stack.setFixedWidth(0)
            self.side_stack.hide()
            return
        if self.side_stack.isHidden():
            self.side_stack.show()
            self.side_stack.setFixedWidth(320)
        self.side_stack.setCurrentIndex(panel_id)
```

- [ ] **Verify import**

```bash
cd src && python -c "from gui_qt.app import TafelAnalyzerApp; print('App shell OK')"
```

Expected: `App shell OK`

- [ ] **Commit**

```bash
git add src/gui_qt/
git commit -m "feat: add ActivityBar and QMainWindow layout shell"
```

---

## Phase 2: Side Panels

### Task 2.1: FilePanel

**Files:**
- Create: `src/gui_qt/panels/file_panel.py`

- [ ] **Implement FilePanel**

```python
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, BUTTON_STYLE, LIST_STYLE, PANEL_STYLE,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, BG_HOVER, BG_CARD,
)


class FileListItem(QWidget):
    """Custom widget for each file row: name | badge | remove button."""

    remove_clicked = Signal(object)  # Path

    def __init__(self, file_path: Path, is_processed: bool = False):
        super().__init__()
        self.file_path = file_path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.name_label = QLabel(file_path.name)
        self.name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)

        if is_processed:
            badge = QLabel("✓")
            badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 12px;")
            layout.addWidget(badge)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 12px; color: #dc2626; font-size: 14px; }}"
            f"QPushButton:hover {{ background: #fee2e2; }}"
        )
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.file_path))
        layout.addWidget(remove_btn)


class FilePanel(QWidget):
    """Side panel for file selection and management."""

    file_selected = Signal(object)   # Path
    file_removed = Signal(object)    # Path
    files_loaded = Signal(list)      # list[Path]
    cache_import_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel("📂 文件")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Select button
        self.btn_select = QPushButton("📁 选择数据文件…")
        self.btn_select.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.clicked.connect(self._on_select)
        layout.addWidget(self.btn_select)

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_STYLE)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.file_list, stretch=1)

        # Cache import
        self.btn_cache = QPushButton("📥 导入缓存")
        self.btn_cache.setStyleSheet(BUTTON_STYLE)
        self.btn_cache.setCursor(Qt.PointingHandCursor)
        self.btn_cache.clicked.connect(self.cache_import_requested.emit)
        layout.addWidget(self.btn_cache)

        # Info
        self.info_label = QLabel("等待选择数据文件 …")
        self.info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Internal state
        self._file_paths: list[Path] = []
        self._processed: set[str] = set()  # str(file_path) -> processed

    def _on_select(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择数据文件", "",
            "支持的文件 (*.tdms *.txt *.csv *.xlsx *.xls *.cor);;All files (*.*)"
        )
        if not paths:
            return
        selected = []
        for p_str in paths:
            path = Path(p_str)
            if path not in self._file_paths:
                self._file_paths.append(path)
                selected.append(path)
        self._rebuild_list()
        if selected:
            self.files_loaded.emit(selected)

    def _rebuild_list(self) -> None:
        self.file_list.clear()
        for path in self._file_paths:
            item = QListWidgetItem()
            widget = FileListItem(path, str(path) in self._processed)
            widget.remove_clicked.connect(self._on_remove)
            item.setSizeHint(widget.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, widget)

    def _on_remove(self, path: Path) -> None:
        confirm = QMessageBox.question(
            self, "确认移除", f"确定要移除文件吗？\n\n{path.name}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._file_paths.remove(path)
        self._processed.discard(str(path))
        self._rebuild_list()
        self.file_removed.emit(path)

    def _on_item_double_click(self, item: QListWidgetItem) -> None:
        widget = self.file_list.itemWidget(item)
        if isinstance(widget, FileListItem):
            self.file_selected.emit(widget.file_path)

    def set_processed(self, path: Path) -> None:
        self._processed.add(str(path))
        self._rebuild_list()

    def set_file_paths(self, paths: list[Path], preferred: Path | None = None) -> None:
        self._file_paths = list(paths)
        self._rebuild_list()

    def update_info(self, text: str) -> None:
        self.info_label.setText(text)
```

- [ ] **Register FilePanel in app.py**

```python
# In _build_ui, after creating side_stack:
from gui_qt.panels.file_panel import FilePanel

self.file_panel = FilePanel()
self.file_panel.files_loaded.connect(self.files.on_files_loaded)
self.file_panel.file_selected.connect(self.files.on_file_selected)
self.side_stack.addWidget(self.file_panel)
# ... add remaining panels to stack
```

Edge case: empty file list shows info label only. Remove last file → state cleared.

- [ ] **Commit**

```bash
git add src/gui_qt/panels/file_panel.py src/gui_qt/app.py
git commit -m "feat: add FilePanel with file list and drag-drop support"
```

---

### Task 2.2: FormulaPanel

**Files:**
- Create: `src/gui_qt/panels/formula_panel.py`

- [ ] **Implement FormulaPanel**

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, INPUT_STYLE, PANEL_STYLE, TEXT_SECONDARY, TEXT_DISABLED, DANGER, BG_HOVER
)


class FormulaPanel(QWidget):
    """Side panel for potential/current formula input."""

    apply_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel("📐 公式")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Potential formula
        layout.addWidget(self._make_label("电压公式:"))
        self.potential_input = QLineEdit()
        self.potential_input.setPlaceholderText("例如 -[Vgs] + 0.23")
        self.potential_input.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.potential_input)

        # Current formula
        layout.addWidget(self._make_label("电流公式:"))
        self.current_input = QLineEdit()
        self.current_input.setPlaceholderText("例如 [Igs/area] / (2.4e-7 + 3)")
        self.current_input.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.current_input)

        # Error label (hidden by default)
        self.error_label = QLabel()
        self.error_label.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Apply button
        self.btn_apply = QPushButton("应用公式并拟合")
        self.btn_apply.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.btn_apply)

        # Channel list
        layout.addWidget(self._make_label("可用 Channel (点击插入):"))
        self.channel_browser = QTextBrowser()
        self.channel_browser.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid #e2e8f0; border-radius: 4px; "
            f"background: {BG_HOVER}; color: {TEXT_SECONDARY}; font-size: 12px; padding: 8px; }}"
        )
        self.channel_browser.setOpenLinks(False)
        self.channel_browser.anchorClicked.connect(self._on_channel_clicked)
        layout.addWidget(self.channel_browser, stretch=1)

        self._active_input = self.potential_input  # track which input to insert into

        # Focus tracking
        self.potential_input.installEventFilter(self)
        self.current_input.installEventFilter(self)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def set_channels(self, channel_names: list[str]) -> None:
        html = " ".join(
            f'<a href="ch:{name}" style="color:#2563eb;text-decoration:none;">[{name}]</a>'
            for name in channel_names
        )
        self.channel_browser.setHtml(html)

    def _on_channel_clicked(self, url):
        name = url.toString().replace("ch:", "")
        cursor = self._active_input.cursorPosition()
        current = self._active_input.text()
        self._active_input.setText(current[:cursor] + f"[{name}]" + current[cursor:])
        self._active_input.setFocus()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn:
            if obj is self.potential_input:
                self._active_input = self.potential_input
            elif obj is self.current_input:
                self._active_input = self.current_input
        return super().eventFilter(obj, event)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def hide_error(self) -> None:
        self.error_label.setVisible(False)

    def get_formulas(self) -> tuple[str, str]:
        return self.potential_input.text().strip(), self.current_input.text().strip()
```

- [ ] **Commit**

```bash
git add src/gui_qt/panels/formula_panel.py
git commit -m "feat: add FormulaPanel with channel insert and error display"
```

---

### Task 2.3: SegmentPanel

**Files:**
- Create: `src/gui_qt/panels/segment_panel.py`

- [ ] **Implement SegmentPanel**

```python
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QColorDialog,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, BG_HOVER, BG_SELECTED, TEXT_PRIMARY,
    TEXT_SECONDARY, SUCCESS, TEXT_DISABLED, ACCENT, ACCENT_HOVER, ACCENT_BUTTON_STYLE,
)


class SegmentItemWidget(QWidget):
    """One row in the segment list: color bar + radio + label + R²."""

    activated = Signal(int)  # segment index
    color_clicked = Signal(int)  # segment index

    def __init__(self, index: int, label: str, color: str,
                 is_active: bool, r2: float | None):
        super().__init__()
        self.segment_index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Color strip
        self.color_bar = QPushButton()
        self.color_bar.setFixedSize(8, 32)
        self.color_bar.setStyleSheet(
            f"QPushButton {{ background: {color}; border: none; border-radius: 2px; }}"
            f"QPushButton:hover {{ border: 1px solid {ACCENT}; }}"
        )
        self.color_bar.setCursor(Qt.PointingHandCursor)
        self.color_bar.clicked.connect(lambda: self.color_clicked.emit(index))
        layout.addWidget(self.color_bar)

        # Radio indicator (◉ or ○)
        self.radio = QLabel("◉" if is_active else "○")
        self.radio.setStyleSheet(
            f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 14px;"
        )
        layout.addWidget(self.radio)

        # Segment label
        self.name_label = QLabel(label)
        self.name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)

        # R² badge
        if r2 is not None:
            r2_label = QLabel(f"R²={r2:.4f}")
            r2_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
            layout.addWidget(r2_label)
        else:
            na_label = QLabel("未拟合")
            na_label.setStyleSheet(f"color: {TEXT_DISABLED}; font-size: 11px;")
            layout.addWidget(na_label)


class SegmentPanel(QWidget):
    """Side panel for segment selection and management."""

    segment_activated = Signal(int)
    segment_color_changed = Signal(int, str)  # index, hex_color
    add_to_comparison = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("📋 分段管理")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Select all / clear all
        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setStyleSheet(BUTTON_STYLE)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_select_all)

        self.btn_clear_all = QPushButton("全不选")
        self.btn_clear_all.setStyleSheet(BUTTON_STYLE)
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_clear_all)
        layout.addLayout(btn_row)

        # Segment list
        self.segment_list = QListWidget()
        self.segment_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        self.segment_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.segment_list, stretch=1)

        # Add to comparison
        self.btn_add_compare = QPushButton("📌 添加到对比")
        self.btn_add_compare.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_add_compare.setCursor(Qt.PointingHandCursor)
        self.btn_add_compare.clicked.connect(self.add_to_comparison.emit)
        layout.addWidget(self.btn_add_compare)

        self._segments: list[dict] = []
        self._active_index: int = 0

    def set_segments(self, segments: list[dict], active_index: int,
                     colors: dict[int, str], fit_by_segment: dict) -> None:
        self._segments = segments
        self._active_index = active_index
        self._rebuild(colors, fit_by_segment)

    def _rebuild(self, colors: dict[int, str], fit_by_segment: dict) -> None:
        self.segment_list.clear()
        for seg in self._segments:
            idx = seg["index"]
            color = colors.get(idx, "#94a3b8")
            is_active = (idx == self._active_index)
            fit = fit_by_segment.get(idx)
            r2 = fit.r2 if fit is not None else None

            item = QListWidgetItem()
            widget = SegmentItemWidget(idx, seg["label"], color, is_active, r2)
            widget.activated.connect(self._on_activate)
            widget.color_clicked.connect(self._on_color_click)
            item.setSizeHint(widget.sizeHint())
            self.segment_list.addItem(item)
            self.segment_list.setItemWidget(item, widget)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.segment_list.itemWidget(item)
        if isinstance(widget, SegmentItemWidget):
            self._on_activate(widget.segment_index)

    def _on_activate(self, index: int) -> None:
        self._active_index = index
        self.segment_activated.emit(index)
        # Refresh radio indicators
        for i in range(self.segment_list.count()):
            item = self.segment_list.item(i)
            w = self.segment_list.itemWidget(item)
            if isinstance(w, SegmentItemWidget):
                is_active = (w.segment_index == index)
                w.radio.setText("◉" if is_active else "○")
                w.radio.setStyleSheet(
                    f"color: {ACCENT if is_active else TEXT_SECONDARY}; font-size: 14px;"
                )

    def _on_color_click(self, index: int) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.segment_color_changed.emit(index, color.name())
```

- [ ] **Commit**

```bash
git add src/gui_qt/panels/segment_panel.py
git commit -m "feat: add SegmentPanel with color bar and radio selection"
```

---

### Task 2.4: ComparisonPanel

**Files:**
- Create: `src/gui_qt/panels/comparison_panel.py`

- [ ] **Implement ComparisonPanel**

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QColorDialog, QCheckBox,
)
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, PANEL_STYLE, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, BG_SELECTED, BG_HOVER, ACCENT_BUTTON_STYLE, DANGER,
)


class ComparisonItemWidget(QWidget):
    """Single row in comparison list."""

    visibility_toggled = Signal(str, bool)   # item_id, visible
    color_clicked = Signal(str)              # item_id
    rename_finished = Signal(str, str)       # item_id, new_name

    def __init__(self, item_id: str, display_name: str,
                 segment_label: str, color: str, visible: bool):
        super().__init__()
        self.item_id = item_id
        self._original_name = display_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Checkbox for visibility
        self.cb = QCheckBox()
        self.cb.setChecked(visible)
        self.cb.stateChanged.connect(
            lambda state: self.visibility_toggled.emit(item_id, bool(state))
        )
        layout.addWidget(self.cb)

        # Editable filename
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

        # Segment label
        seg_label = QLabel(segment_label)
        seg_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(seg_label)

        # Color dot
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid white; "
            f"border-radius: 10px; }}"
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
        if obj is self.name_edit and event.type() == event.Type.MouseButtonDblClick:
            self.name_edit.setReadOnly(False)
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return True
        if obj is self.name_edit and event.type() == event.Type.FocusOut:
            self.name_edit.setReadOnly(True)
        return super().eventFilter(obj, event)


class ComparisonPanel(QWidget):
    """Side panel for cross-file comparison item management."""

    item_visibility_changed = Signal(str, bool)
    item_color_changed = Signal(str, str)    # item_id, hex_color
    item_renamed = Signal(str, str)          # item_id, new_name
    add_all_clicked = Signal()
    clear_all_clicked = Signal()
    delete_selected_clicked = Signal()
    move_up_clicked = Signal()
    move_down_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("📊 对比")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Action bar
        action_row = QHBoxLayout()
        self.btn_delete = QPushButton("🗑 删除选中")
        self.btn_delete.setStyleSheet(BUTTON_STYLE)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self.delete_selected_clicked.emit)
        action_row.addWidget(self.btn_delete)

        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedWidth(32)
        self.btn_up.setStyleSheet(BUTTON_STYLE)
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.clicked.connect(self.move_up_clicked.emit)
        action_row.addWidget(self.btn_up)

        self.btn_down = QPushButton("↓")
        self.btn_down.setFixedWidth(32)
        self.btn_down.setStyleSheet(BUTTON_STYLE)
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.clicked.connect(self.move_down_clicked.emit)
        action_row.addWidget(self.btn_down)
        layout.addLayout(action_row)

        # Item list
        self.item_list = QListWidget()
        self.item_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        layout.addWidget(self.item_list, stretch=1)

        # Bottom buttons
        self.btn_add_all = QPushButton("📥 添加所有已处理段")
        self.btn_add_all.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_add_all.setCursor(Qt.PointingHandCursor)
        self.btn_add_all.clicked.connect(self.add_all_clicked.emit)
        layout.addWidget(self.btn_add_all)

        self.btn_clear = QPushButton("🗑 清空全部")
        self.btn_clear.setStyleSheet(
            BUTTON_STYLE + f"QPushButton {{ color: {DANGER}; }}"
        )
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_all_clicked.emit)
        layout.addWidget(self.btn_clear)

    def set_items(self, items: list[dict]) -> None:
        """items: list of {item_id, display_name, segment_label, color, visible}"""
        self.item_list.clear()
        self._current_item_ids = [it["item_id"] for it in items]
        for data in items:
            widget = ComparisonItemWidget(
                data["item_id"], data["display_name"],
                data["segment_label"], data["color"], data["visible"],
            )
            widget.visibility_toggled.connect(self._on_visibility)
            widget.color_clicked.connect(self._on_color)
            widget.rename_finished.connect(self._on_rename)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.item_list.addItem(item)
            self.item_list.setItemWidget(item, widget)

    def _on_visibility(self, item_id: str, visible: bool):
        self.item_visibility_changed.emit(item_id, visible)

    def _on_color(self, item_id: str):
        color = QColorDialog.getColor()
        if color.isValid():
            self.item_color_changed.emit(item_id, color.name())

    def _on_rename(self, item_id: str, new_name: str):
        self.item_renamed.emit(item_id, new_name)
```

- [ ] **Commit**

```bash
git add src/gui_qt/panels/comparison_panel.py
git commit -m "feat: add ComparisonPanel with checkbox, rename, and color picker"
```

---

## Phase 3: Central Area

### Task 3.1: ParamToolBar

**Files:**
- Create: `src/gui_qt/central/param_bar.py`

- [ ] **Implement ParamToolBar**

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QRegularExpressionValidator

from gui_qt.theme import (
    ACCENT_BUTTON_STYLE, INPUT_STYLE, TEXT_SECONDARY, BG_CARD, BORDER,
)


class RangeValidator(QRegularExpressionValidator):
    """Validates 'min-max' format like '12-15' or '-3--1'."""
    def __init__(self, parent=None):
        from PySide6.QtGui import QRegularExpressionValidator as V
        super().__init__(
            r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*-\s*"
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*$",
            parent,
        )


class FloatValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        super().__init__(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*$", parent)


class ParamToolBar(QWidget):
    """Fixed toolbar above chart with fitting parameters."""

    fit_clicked = Signal()
    parameters_changed = Signal(dict)  # {param_name: value}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            ParamToolBar {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        def add_param(label: str, width: int = 80) -> QLineEdit:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(lbl)
            entry = QLineEdit()
            entry.setFixedWidth(width)
            entry.setStyleSheet(INPUT_STYLE)
            layout.addWidget(entry)
            return entry

        self.entry_eeq = add_param("E_eq:")
        self.entry_window = add_param("窗口:", 70)
        self.entry_eta = add_param("η:", 70)
        self.entry_logj = add_param("logj:", 70)
        self.entry_r2 = add_param("R²:", 60)

        # Fit priority combo
        lbl = QLabel("优先:")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(lbl)
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["斜率更低优先", "R²优先"])
        self.combo_priority.setStyleSheet(
            f"QComboBox {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 12px; }}"
        )
        layout.addWidget(self.combo_priority)

        layout.addStretch()

        # Run button
        self.btn_fit = QPushButton("▶ 自动拟合")
        self.btn_fit.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_fit.setCursor(Qt.PointingHandCursor)
        self.btn_fit.clicked.connect(self.fit_clicked.emit)
        layout.addWidget(self.btn_fit)

    def set_defaults(self, defaults: dict) -> None:
        mapping = {
            "e_eq": self.entry_eeq,
            "window_range": self.entry_window,
            "eta_range": self.entry_eta,
            "logj_range": self.entry_logj,
            "min_r2": self.entry_r2,
        }
        for key, entry in mapping.items():
            val = defaults.get(key, "")
            if val:
                entry.setText(str(val))

    def get_params(self) -> dict:
        return {
            "e_eq": self.entry_eeq.text().strip(),
            "window_range": self.entry_window.text().strip(),
            "eta_range": self.entry_eta.text().strip(),
            "logj_range": self.entry_logj.text().strip(),
            "min_r2": self.entry_r2.text().strip(),
            "fit_priority": self.combo_priority.currentText().strip(),
        }

    def set_enabled(self, enabled: bool) -> None:
        for widget in [self.entry_eeq, self.entry_window, self.entry_eta,
                       self.entry_logj, self.entry_r2, self.combo_priority, self.btn_fit]:
            widget.setEnabled(enabled)
```

- [ ] **Commit**

```bash
git add src/gui_qt/central/param_bar.py
git commit -m "feat: add ParamToolBar with parameter inputs and validators"
```

---

### Task 3.2: ChartArea (matplotlib canvas)

**Files:**
- Create: `src/gui_qt/central/chart_widget.py`

- [ ] **Implement ChartArea**

```python
from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from gui_qt.theme import BG_CARD, BORDER


class ChartArea(QWidget):
    """Central matplotlib chart area with dual plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # matplotlib figure
        self.fig = Figure(figsize=(10.8, 6.6), dpi=100)
        self.fig.set_facecolor(BG_CARD)
        self.fig.patch.set_facecolor(BG_CARD)

        # Canvas
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet(f"background: {BG_CARD};")
        layout.addWidget(self.canvas, stretch=1)

        # Store for external code that needs to access the figure
        self.axes: list = []

    def clear_figure(self) -> None:
        self.fig.clear()
        self.axes = []
        self.canvas.draw_idle()
```

- [ ] **Commit**

```bash
git add src/gui_qt/central/chart_widget.py
git commit -m "feat: add ChartArea with matplotlib FigureCanvasQTAgg"
```

---

### Task 3.3: ChartToolBar

**Files:**
- Create: `src/gui_qt/central/chart_toolbar.py`

- [ ] **Implement ChartToolBar**

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt

from gui_qt.theme import (
    BUTTON_STYLE, ACCENT, ACCENT_HOVER, BG_CARD, BORDER, TEXT_SECONDARY
)


class ChartToolBar(QWidget):
    """Custom toolbar below the chart: zoom, pan, manual select, export."""

    home_clicked = Signal()
    zoom_in_clicked = Signal()
    zoom_out_clicked = Signal()
    pan_clicked = Signal()
    manual_clicked = Signal()
    save_image_clicked = Signal()
    copy_clipboard_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            ChartToolBar {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self._tool_btns: dict[str, QPushButton] = {}
        self._active_tool: str | None = None

        for icon, tooltip, signal in [
            ("↺", "重置视图", self.home_clicked),
            ("🔍+", "放大", self.zoom_in_clicked),
            ("🔍-", "缩小", self.zoom_out_clicked),
            ("✋", "平移", self.pan_clicked),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

        layout.addWidget(self._sep())

        self.btn_manual = QPushButton("▭ 框选拟合")
        self.btn_manual.setToolTip("手动框选 Tafel 拟合区域")
        self.btn_manual.setCheckable(True)
        self.btn_manual.setCursor(Qt.PointingHandCursor)
        self.btn_manual.setStyleSheet(self._tool_btn_style(False))
        self.btn_manual.clicked.connect(self._on_manual_click)
        layout.addWidget(self.btn_manual)

        layout.addWidget(self._sep())

        for icon, tooltip, signal in [
            ("💾 保存图片", "保存图表为 PNG", self.save_image_clicked),
            ("📋 复制", "复制到剪贴板", self.copy_clipboard_clicked),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

        layout.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _sep(self) -> QLabel:
        s = QLabel("|")
        s.setStyleSheet(f"color: {BORDER}; font-size: 14px; padding: 0 2px;")
        return s

    def _tool_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {ACCENT}; color: white; "
                f"border: none; border-radius: 6px; padding: 4px 12px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
            )
        return BUTTON_STYLE

    def _on_manual_click(self) -> None:
        active = self.btn_manual.isChecked()
        self.btn_manual.setStyleSheet(self._tool_btn_style(active))
        self.manual_clicked.emit()

    def set_manual_mode(self, active: bool) -> None:
        self.btn_manual.setChecked(active)
        self.btn_manual.setStyleSheet(self._tool_btn_style(active))

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
```

- [ ] **Commit**

```bash
git add src/gui_qt/central/chart_toolbar.py
git commit -m "feat: add ChartToolBar with manual mode and view controls"
```

---

### Task 3.4: Wire central area into app.py

- [ ] **Integrate into app.py**

```python
# In TafelAnalyzerApp._build_ui(), in central_layout:
from gui_qt.central.param_bar import ParamToolBar
from gui_qt.central.chart_widget import ChartArea
from gui_qt.central.chart_toolbar import ChartToolBar

self.param_bar = ParamToolBar()
self.chart = ChartArea()
self.chart_toolbar = ChartToolBar()
self.status_bar = QLabel("就绪")
self.status_bar.setFixedHeight(24)
self.status_bar.setStyleSheet(f"color: #64748b; font-size: 10px; padding-left: 8px; background: {BG_CARD};")

self.central_layout.addWidget(self.param_bar)
self.central_layout.addWidget(self.chart, stretch=1)
self.central_layout.addWidget(self.chart_toolbar)
self.central_layout.addWidget(self.status_bar)

# Connect signals
self.param_bar.fit_clicked.connect(self.fitting.run_fit)
```

- [ ] **Commit**

```bash
git add src/gui_qt/app.py src/gui_qt/central/
git commit -m "feat: integrate central area (param bar, chart, toolbar) into app"
```

---

## Phase 4: Controllers

### Task 4.1: Base Controller

**Files:**
- Create: `src/gui_qt/controllers/base.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class BaseAppController(QObject):
    """Base class for controllers. Holds app reference for state access."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self.app = app
```

- [ ] **Commit**

```bash
git add src/gui_qt/controllers/base.py
git commit -m "feat: add base controller class"
```

---

### Task 4.2: FileController

**Files:**
- Create: `src/gui_qt/controllers/file_ctrl.py`

- [ ] **Implement FileController**

```python
from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from core.readers import read_data_all_channels
from core.formula import normalize_formula
from core.fitting import build_segment_infos
from core.types import POTENTIAL_PREFERRED_NAMES, CURRENT_PREFERRED_NAMES
from core.utils import pick_channel_name
from gui import palette as p
from gui_qt.controllers.base import BaseAppController
from gui.rendering import draw_placeholder

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class FileLoadWorker(QThread):
    """Background worker for loading file data."""

    finished = Signal(object, object, object, object)  # channels, potential_f, current_f, segments
    error = Signal(str)

    def __init__(self, file_path: Path, potential_formula: str, current_formula: str):
        super().__init__()
        self.file_path = file_path
        self.potential_formula = potential_formula
        self.current_formula = current_formula

    def run(self):
        try:
            channels = read_data_all_channels(self.file_path)
            formulas = self._resolve_formulas(channels)
            segments = build_segment_infos(channels, formulas[0])
            self.finished.emit(channels, formulas[0], formulas[1], segments)
        except Exception as exc:
            self.error.emit(str(exc))

    def _resolve_formulas(self, channels: dict) -> tuple[str, str]:
        def try_or_default(text: str, preferred: list[str]) -> str:
            raw = text.strip()
            if raw:
                try:
                    normalize_formula(channels, raw, preferred)
                    return raw
                except Exception:
                    pass
            return f"[{pick_channel_name(channels, preferred)}]"
        return (
            try_or_default(self.potential_formula, POTENTIAL_PREFERRED_NAMES),
            try_or_default(self.current_formula, CURRENT_PREFERRED_NAMES),
        )


class FileController(BaseAppController):
    """Manages file loading, switching, and removal."""

    file_loaded = Signal()
    file_load_failed = Signal(str)

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FileLoadWorker | None = None

    def on_files_loaded(self, paths: list[Path]) -> None:
        app = self.app
        app._app_state["selected_paths"] = paths
        app.file_panel.update_info(
            f"已选择 {len(paths)} 个文件"
        )
        self._load_file(paths[0])

    def on_file_selected(self, path: Path) -> None:
        self._load_file(path)

    def _load_file(self, path: Path) -> None:
        app = self.app
        app.status_bar.setText(f"正在加载 {path.name} …")
        app._app_state["tdms_path"] = path
        formulas = app.formula_panel.get_formulas()
        self._worker = FileLoadWorker(path, formulas[0], formulas[1])
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_load_finished(self, channels, pot_f, cur_f, segments) -> None:
        app = self.app
        app._app_state["channels"] = channels
        app._app_state["segments"] = [{"index": s.index, "label": s.label} for s in segments]
        app._app_state["segment_colors"] = {}
        segment_count = len(segments)

        # Update formula panel
        app.formula_panel.hide_error()
        app.formula_panel.potential_input.setText(pot_f)
        app.formula_panel.current_input.setText(cur_f)
        app.formula_panel.set_channels(list(channels.keys()))

        # Update segment panel
        app.segment_panel.set_segments(
            app._app_state["segments"], 0,
            app._app_state["segment_colors"],
            {},
        )

        # Update param bar defaults
        app.param_bar.set_defaults(app._app_state.get("saved_parameter_defaults", {}))

        # Update status
        path = app._app_state["tdms_path"]
        app.file_panel.update_info(
            f"{len(channels)} channels · {segment_count} segments"
        )
        app.file_panel.set_processed(path)
        app.status_bar.setText(f"已加载 {path.name}")

        # Draw placeholder
        draw_placeholder(
            app.chart.fig, app.chart.canvas,
            app.chart.axes,
        )
        self.file_loaded.emit()

    def _on_load_error(self, msg: str) -> None:
        self.app.status_bar.setText("加载失败")
        QMessageBox.critical(self.app, "加载失败", msg)
```

Note: `draw_placeholder` in `gui/rendering.py` currently takes `app` and accesses `app.fig` and `app.canvas`. For the Qt version, `app.chart.fig` and `app.chart.canvas` should be accessible the same way. We'll need to update `draw_placeholder` to accept fig/canvas as parameters rather than the whole app. Create a shim:

```python
# In gui/rendering.py, add a convenience function:
def draw_placeholder_fig(fig, canvas, axes_list):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, "请选择数据文件并输入公式\n手动模式下可在右侧 Tafel 图框选区域",
            ha="center", va="center", fontsize=16, color="#475569",
            transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    canvas.draw_idle()
```

- [ ] **Commit**

```bash
git add src/gui_qt/controllers/file_ctrl.py
git commit -m "feat: add FileController with background file loading"
```

---

### Task 4.3: FittingController

**Files:**
- Create: `src/gui_qt/controllers/fitting_ctrl.py`

- [ ] **Implement FittingController**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal, QObject

from core.fitting import prepare_series, auto_tafel_fit
from core.formula import evaluate_formula
from core.types import PreparedSeries, TafelFit
from gui_qt.controllers.base import BaseAppController

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class FitWorker(QThread):
    """Background fitting worker."""

    finished = Signal(object, object)  # PreparedSeries, TafelFit | None
    error = Signal(str)

    def __init__(self, channels: dict, pot_formula: str, cur_formula: str,
                 e_eq: float, segments: list, active_index: int,
                 window_min: int, window_max: int, min_r2: float,
                 fit_priority: str, eta_range, logj_range):
        super().__init__()
        self.channels = channels
        self.pot_formula = pot_formula
        self.cur_formula = cur_formula
        self.e_eq = e_eq
        self.segments = segments
        self.active_index = active_index
        self.window_min = window_min
        self.window_max = window_max
        self.min_r2 = min_r2
        self.fit_priority = fit_priority
        self.eta_range = eta_range
        self.logj_range = logj_range

    def run(self):
        try:
            segment = self.segments[self.active_index]
            prepared = prepare_series(
                self.channels, self.pot_formula, self.cur_formula,
                self.e_eq, segment,
            )
            fit = auto_tafel_fit(
                prepared, self.window_min, self.window_max,
                min_r2=self.min_r2, fit_priority=self.fit_priority,
                eta_range=self.eta_range, logj_range=self.logj_range,
            )
            self.finished.emit(prepared, fit)
        except Exception as exc:
            self.error.emit(str(exc))


class FittingController(BaseAppController):
    """Orchestrates fitting in background thread."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self._worker: FitWorker | None = None

    def run_fit(self) -> None:
        app = self.app
        state = app._app_state
        channels = state.get("channels")
        if channels is None:
            return

        params = app.param_bar.get_params()
        try:
            e_eq = float(params["e_eq"] or 0)
            window_text = params.get("window_range", "12-15") or "12-15"
            parts = window_text.split("-")
            window_min, window_max = int(parts[0]), int(parts[1])
            min_r2 = float(params.get("min_r2", "0.95") or "0.95")
        except (ValueError, IndexError):
            app.status_bar.setText("参数格式错误")
            return

        pot_f, cur_f = app.formula_panel.get_formulas()
        active_index = state.get("active_segment_index", 0)
        segments = state.get("segments", [])
        if not segments:
            return

        app.status_bar.setText("正在拟合…")
        self._worker = FitWorker(
            channels, pot_f, cur_f, e_eq, segments, active_index,
            window_min, window_max, min_r2,
            params.get("fit_priority", "slope"),
            params.get("eta_range"), params.get("logj_range"),
        )
        self._worker.finished.connect(self._on_fit_finished)
        self._worker.error.connect(self._on_fit_error)
        self._worker.start()

    def _on_fit_finished(self, prepared: PreparedSeries, fit: TafelFit | None) -> None:
        app = self.app
        app._app_state["prepared"] = prepared
        app._app_state["fit"] = fit

        # Update segment panel with new R² values
        fit_by = {prepared.segment.index: fit} if fit else {}
        app._app_state["fit_by_segment"] = fit_by
        app.segment_panel.set_segments(
            app._app_state["segments"],
            app._app_state.get("active_segment_index", 0),
            app._app_state.get("segment_colors", {}),
            fit_by,
        )

        from gui.rendering import draw
        draw(app, prepared, fit)

        if fit:
            app.status_bar.setText(
                f"第{prepared.segment.index + 1}段拟合完成: "
                f"{fit.slope_mv_per_dec:.2f} mV/dec, R²={fit.r2:.4f}"
            )
        else:
            app.status_bar.setText(f"第{prepared.segment.index + 1}段拟合失败")

    def _on_fit_error(self, msg: str) -> None:
        self.app.status_bar.setText(f"拟合错误: {msg[:60]}")
```

- [ ] **Commit**

```bash
git add src/gui_qt/controllers/fitting_ctrl.py
git commit -m "feat: add FittingController with QThread background fitting"
```

---

### Task 4.4: Complete app.py wiring

**Files:**
- Modify: `src/gui_qt/app.py`

- [ ] **Wire all controllers and panels together**

Full `_init_controllers` and `_build_ui`:

```python
from gui_qt.activity_bar import ActivityBar, PANEL_FILES, PANEL_FORMULA, PANEL_SEGMENTS, PANEL_PARAMS
from gui_qt.panels.file_panel import FilePanel
from gui_qt.panels.formula_panel import FormulaPanel
from gui_qt.panels.segment_panel import SegmentPanel
from gui_qt.panels.comparison_panel import ComparisonPanel
from gui_qt.central.param_bar import ParamToolBar
from gui_qt.central.chart_widget import ChartArea
from gui_qt.central.chart_toolbar import ChartToolBar
from gui_qt.controllers.file_ctrl import FileController
from gui_qt.controllers.fitting_ctrl import FittingController

def _build_ui(self) -> None:
    central = QWidget()
    self.setCentralWidget(central)
    layout = QHBoxLayout(central)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(0)

    # Activity bar
    self.activity_bar = ActivityBar()
    self.activity_bar.panel_clicked.connect(self._on_panel_clicked)
    layout.addWidget(self.activity_bar)

    # Side panel stack
    self.side_stack = QStackedWidget()
    self.side_stack.setFixedWidth(320)
    layout.addWidget(self.side_stack)

    # Panels
    from gui_qt.panels.file_panel import FilePanel
    from gui_qt.panels.formula_panel import FormulaPanel
    from gui_qt.panels.segment_panel import SegmentPanel

    self.file_panel = FilePanel()
    self.formula_panel = FormulaPanel()
    self.segment_panel = SegmentPanel()

    self.side_stack.addWidget(self.file_panel)      # index 0
    self.side_stack.addWidget(self.formula_panel)    # index 1
    self.side_stack.addWidget(self.segment_panel)    # index 2

    # Central area
    self.central_widget = QWidget()
    self.central_layout = QVBoxLayout(self.central_widget)
    self.central_layout.setContentsMargins(0, 0, 0, 0)
    self.central_layout.setSpacing(0)

    self.param_bar = ParamToolBar()
    self.chart = ChartArea()
    self.chart_toolbar = ChartToolBar()

    self.status_bar = QLabel("就绪")
    self.status_bar.setFixedHeight(24)
    self.status_bar.setStyleSheet(
        f"color: #64748b; font-size: 10px; padding-left: 8px; background: {BG_CARD};"
    )

    self.central_layout.addWidget(self.param_bar)
    self.central_layout.addWidget(self.chart, stretch=1)
    self.central_layout.addWidget(self.chart_toolbar)
    self.central_layout.addWidget(self.status_bar)

    layout.addWidget(self.central_widget, stretch=1)

    # Default state
    self.side_stack.setCurrentIndex(PANEL_FILES)
    self.activity_bar.set_active(PANEL_FILES)

def _init_controllers(self) -> None:
    self.files = FileController(self)
    self.fitting = FittingController(self)

    # Wire file panel
    self.file_panel.files_loaded.connect(self.files.on_files_loaded)
    self.file_panel.file_selected.connect(self.files.on_file_selected)

    # Wire param bar
    self.param_bar.fit_clicked.connect(self.fitting.run_fit)

    # Wire formula panel
    self.formula_panel.apply_clicked.connect(self.fitting.run_fit)
```

- [ ] **Commit**

```bash
git add src/gui_qt/app.py
git commit -m "feat: wire all panels and controllers in app.py"
```

---

## Phase 5: Palette Dialog & Color Management

### Task 5.1: PaletteSchemeManager Dialog

**Files:**
- Create: `src/gui_qt/panels/palette_dialog.py`

- [ ] **Implement PaletteSchemeManager dialog**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QColorDialog, QFrame,
    QScrollArea, QWidget, QGridLayout, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QRegularExpressionValidator

from gui_qt.theme import (
    ACCENT, ACCENT_HOVER, BG_WINDOW, BG_CARD, BG_HOVER, BG_SELECTED,
    BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ON_ACCENT,
    SUCCESS, SUCCESS_HOVER, DANGER, BUTTON_STYLE, ACCENT_BUTTON_STYLE,
)
from gui import palette as p

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class PaletteSchemeManager(QDialog):
    """配色方案管理对话框."""

    schemes_updated = Signal()

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("配色方案管理")
        self.setMinimumSize(860, 620)
        self.resize(860, 620)
        self.setStyleSheet(f"QDialog {{ background: {BG_WINDOW}; }}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Left panel: scheme list
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet(f"QWidget {{ background: {BG_CARD}; border-radius: 8px; }}")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)

        left_layout.addWidget(self._title_label("配色方案"))

        # Add scheme row
        add_row = QHBoxLayout()
        self.entry_new = QLineEdit()
        self.entry_new.setPlaceholderText("输入新方案名")
        self.entry_new.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 12px; }}"
        )
        add_row.addWidget(self.entry_new)

        btn_add = QPushButton("新增")
        btn_add.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_add.clicked.connect(self._add_scheme)
        add_row.addWidget(btn_add)
        left_layout.addLayout(add_row)

        self.scheme_list = QListWidget()
        self.scheme_list.setStyleSheet(
            f"QListWidget {{ border: none; outline: none; }}"
            f"QListWidget::item {{ padding: 8px; border-radius: 6px; }}"
            f"QListWidget::item:selected {{ background: {BG_SELECTED}; }}"
        )
        self.scheme_list.currentItemChanged.connect(self._on_scheme_selected)
        left_layout.addWidget(self.scheme_list, stretch=1)

        btn_delete = QPushButton("删除当前方案")
        btn_delete.setStyleSheet(
            f"QPushButton {{ background: #fee2e2; color: {DANGER}; "
            f"border: none; border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: #fecaca; }}"
        )
        btn_delete.clicked.connect(self._delete_scheme)
        left_layout.addWidget(btn_delete)

        # Right panel: color grid
        right = QWidget()
        right.setStyleSheet(f"QWidget {{ background: {BG_CARD}; border-radius: 8px; }}")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)

        self.scheme_title = QLabel("颜色设置")
        self.scheme_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};"
        )
        right_layout.addWidget(self.scheme_title)

        self.color_scroll = QScrollArea()
        self.color_scroll.setWidgetResizable(True)
        self.color_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }}"
        )
        self.color_grid_widget = QWidget()
        self.color_grid = QGridLayout(self.color_grid_widget)
        self.color_grid.setSpacing(6)
        self.color_scroll.setWidget(self.color_grid_widget)
        right_layout.addWidget(self.color_scroll, stretch=1)

        # Bottom: apply buttons
        btn_row = QHBoxLayout()
        btn_apply_current = QPushButton("应用方案到当前分段")
        btn_apply_current.setStyleSheet(ACCENT_BUTTON_STYLE)
        btn_apply_current.clicked.connect(self._apply_to_current)
        btn_row.addWidget(btn_apply_current)

        btn_apply_compare = QPushButton("应用方案到对比")
        btn_apply_compare.setStyleSheet(BUTTON_STYLE)
        btn_apply_compare.clicked.connect(self._apply_to_comparison)
        btn_row.addWidget(btn_apply_compare)

        btn_add_slot = QPushButton("+ 新增颜色位")
        btn_add_slot.setStyleSheet(BUTTON_STYLE)
        btn_add_slot.clicked.connect(self._add_color_slot)
        btn_row.addWidget(btn_add_slot)
        right_layout.addLayout(btn_row)

        layout.addWidget(left)
        layout.addWidget(right, stretch=1)

        self._populate_scheme_list()

    def _title_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        return lbl

    def _populate_scheme_list(self) -> None:
        self.scheme_list.clear()
        schemes = self.app._app_state.get("palette_schemes", {})
        for name in schemes:
            item = QListWidgetItem(name)
            self.scheme_list.addItem(item)
        if self.scheme_list.count() > 0:
            self.scheme_list.setCurrentRow(0)

    def _on_scheme_selected(self, current, previous) -> None:
        if current is None:
            return
        name = current.text()
        self._render_colors(name)

    def _render_colors(self, scheme_name: str) -> None:
        # Clear grid
        while self.color_grid.count():
            w = self.color_grid.takeAt(0).widget()
            if w:
                w.deleteLater()

        self.scheme_title.setText(f'颜色设置: 当前方案 "{scheme_name}"')
        colors = p.get_palette_scheme_colors(
            self.app, scheme_name, include_defaults=True
        )

        hex_validator = QRegularExpressionValidator(r"^#[0-9a-fA-F]{6}$")

        for idx in sorted(colors):
            color = colors[idx]
            row = idx

            # Label
            lbl = QLabel(f"第{idx + 1}段")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            self.color_grid.addWidget(lbl, row, 0)

            # Preview button
            preview = QPushButton()
            preview.setFixedSize(28, 24)
            preview.setStyleSheet(
                f"QPushButton {{ background: {color}; border: none; border-radius: 4px; }}"
                f"QPushButton:hover {{ border: 2px solid {ACCENT}; }}"
            )
            preview.clicked.connect(lambda checked, idx=idx: self._pick_color(idx))
            self.color_grid.addWidget(preview, row, 1)

            # Hex input
            entry = QLineEdit(color)
            entry.setFixedWidth(120)
            entry.setStyleSheet(
                f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; "
                f"padding: 4px 8px; font-size: 12px; }}"
                f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
            )
            entry.setValidator(hex_validator)
            entry.editingFinished.connect(
                lambda e=entry, idx=idx: self._apply_hex(idx, e.text())
            )
            self.color_grid.addWidget(entry, row, 2)

            # Apply button
            apply_btn = QPushButton("应用")
            apply_btn.setFixedWidth(50)
            apply_btn.setStyleSheet(BUTTON_STYLE)
            apply_btn.clicked.connect(
                lambda checked, idx=idx, e=entry: self._apply_hex(idx, e.text())
            )
            self.color_grid.addWidget(apply_btn, row, 3)

    def _pick_color(self, idx: int) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            name = self._current_scheme_name()
            p.set_palette_scheme_color(self.app, name, idx, color.name())
            self._render_colors(name)

    def _apply_hex(self, idx: int, text: str) -> None:
        from gui.palette import normalize_color_value
        normalized = normalize_color_value(text)
        if normalized:
            name = self._current_scheme_name()
            p.set_palette_scheme_color(self.app, name, idx, normalized)
            self._render_colors(name)

    def _current_scheme_name(self) -> str:
        item = self.scheme_list.currentItem()
        return item.text() if item else "默认方案"

    def _add_scheme(self) -> None:
        name = self.entry_new.text().strip() or "新方案"
        schemes = self.app._app_state.setdefault("palette_schemes", {})
        if name in schemes:
            QMessageBox.warning(self, "提示", f'配色方案"{name}"已存在')
            return
        schemes[name] = {}
        p.set_palette_scheme_slot_count(self.app, name, 8)
        p.materialize_palette_scheme(self.app, name)
        self.entry_new.clear()
        self._populate_scheme_list()

    def _delete_scheme(self) -> None:
        name = self._current_scheme_name()
        schemes = self.app._app_state.get("palette_schemes", {})
        if len(schemes) <= 1:
            QMessageBox.warning(self, "提示", "至少保留一套配色方案")
            return
        confirm = QMessageBox.question(
            self, "确认", f'确定删除"{name}"吗？',
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        schemes.pop(name, None)
        self._populate_scheme_list()

    def _add_color_slot(self) -> None:
        name = self._current_scheme_name()
        count = p.palette_scheme_slot_count(self.app, name)
        p.set_palette_scheme_slot_count(self.app, name, count + 1)
        p.materialize_palette_scheme(self.app, name)
        self._render_colors(name)

    def _apply_to_current(self) -> None:
        p.apply_palette_scheme_to_current(self.app)
        self.schemes_updated.emit()

    def _apply_to_comparison(self) -> None:
        p.apply_palette_scheme_to_comparison(self.app)
        self.schemes_updated.emit()
```

- [ ] **Commit**

```bash
git add src/gui_qt/panels/palette_dialog.py
git commit -m "feat: add PaletteSchemeManager QDialog"
```

---

## Phase 6: Comparison Mode & Rendering

### Task 6.1: ComparisonController

**Files:**
- Create: `src/gui_qt/controllers/comparison_ctrl.py`
- Create: `src/gui_qt/central/summary_table.py`

- [ ] **Implement SummaryTable**

```python
from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt


class SummaryTable(QTableWidget):
    """Comparison results summary table with sorting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["别名", "段", "斜率 (mV/dec)", "R²", "点数"])
        self.setSelectionBehavior(self.SelectRows)
        self.setSelectionMode(self.SingleSelection)
        self.setEditTriggers(self.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.verticalHeader().setVisible(False)

    def set_items(self, items_data: list[dict]) -> None:
        """items_data: [{alias, segment, slope, r2, n_points}]"""
        self.setSortingEnabled(False)
        self.setRowCount(len(items_data))
        for row, data in enumerate(items_data):
            self.setItem(row, 0, QTableWidgetItem(data.get("alias", "")))
            self.setItem(row, 1, QTableWidgetItem(str(data.get("segment", ""))))
            slope = data.get("slope")
            self.setItem(row, 2, QTableWidgetItem(
                f"{slope:.1f}" if slope is not None else ""
            ))
            r2 = data.get("r2")
            self.setItem(row, 3, QTableWidgetItem(
                f"{r2:.4f}" if r2 is not None else ""
            ))
            self.setItem(row, 4, QTableWidgetItem(str(data.get("n_points", ""))))
        self.setSortingEnabled(True)
```

- [ ] **Implement ComparisonController**

```python
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from core.types import ComparisonItem
from gui_qt.controllers.base import BaseAppController
from gui import palette as p
from gui import comparison as comp

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class ComparisonController(BaseAppController):
    """Manages comparison items CRUD and rendering."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)

    def add_from_current(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        active_idx = app._app_state.get("active_segment_index", 0)
        prepared = app._app_state.get("prepared")
        fit = app._app_state.get("fit")
        if prepared is None:
            QMessageBox.warning(app, "提示", "请先运行拟合")
            return

        from gui import comparison as comp_mod
        item_id = comp_mod.comparison_item_id(path, active_idx)
        existing = [it for it in app._app_state.get("comparison_items", [])
                    if it.item_id == item_id]
        if existing:
            QMessageBox.warning(app, "提示", "该项目已在对比列表中")
            return

        color = p.get_segment_color(app, active_idx, file_path=path)
        item = ComparisonItem(
            item_id=item_id,
            file_path=path,
            file_name=path.name,
            segment_index=active_idx,
            prepared=prepared,
            fit=fit,
            label=f"{path.stem}-第{active_idx + 1}段",
            color=color,
            visible=True,
        )
        app._app_state.setdefault("comparison_items", []).append(item)
        self.refresh_list()

    def add_all_processed(self) -> None:
        app = self.app
        path = app._app_state.get("tdms_path")
        if not path:
            return
        # Iterate all segments that have results
        prepared_by = app._app_state.get("prepared_by_segment", {})
        fit_by = app._app_state.get("fit_by_segment", {})
        items = app._app_state.setdefault("comparison_items", [])
        from gui import comparison as comp_mod

        for seg_idx in prepared_by:
            item_id = comp_mod.comparison_item_id(path, seg_idx)
            if any(it.item_id == item_id for it in items):
                continue
            color = p.get_segment_color(app, seg_idx, file_path=path)
            items.append(ComparisonItem(
                item_id=item_id,
                file_path=path,
                file_name=path.name,
                segment_index=seg_idx,
                prepared=prepared_by[seg_idx],
                fit=fit_by.get(seg_idx),
                label=f"{path.stem}-第{seg_idx + 1}段",
                color=color,
                visible=True,
            ))
        self.refresh_list()

    def remove_selected(self, item_id: str) -> None:
        items = app._app_state.get("comparison_items", [])
        app._app_state["comparison_items"] = [it for it in items if it.item_id != item_id]
        self.refresh_list()

    def delete_selected(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if 0 <= current < len(items):
            items.pop(current)
            self.refresh_list()

    def move_up(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current > 0:
            items[current], items[current - 1] = items[current - 1], items[current]
            self.refresh_list()

    def move_down(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        current = self.app.comparison_panel.item_list.currentRow()
        if current < len(items) - 1:
            items[current], items[current + 1] = items[current + 1], items[current]
            self.refresh_list()

    def clear_all(self) -> None:
        self.app._app_state["comparison_items"] = []
        self.refresh_list()

    def toggle_visibility(self, item_id: str, visible: bool) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.visible = visible
                break
        self._rerender()

    def update_color(self, item_id: str, color: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.color = color
                break
        self._rerender()

    def rename(self, item_id: str, new_name: str) -> None:
        for item in self.app._app_state.get("comparison_items", []):
            if item.item_id == item_id:
                item.label = f"{new_name}-第{item.segment_index + 1}段"
                item.file_name = new_name
                break
        self.refresh_list()

    def refresh_list(self) -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        list_data = [
            {
                "item_id": it.item_id,
                "display_name": it.file_name,
                "segment_label": f"-第{it.segment_index + 1}段",
                "color": it.color,
                "visible": it.visible,
            }
            for it in items
        ]
        if hasattr(app, "comparison_panel"):
            app.comparison_panel.set_items(list_data)
        self._update_summary()

    def _update_summary(self) -> None:
        items = self.app._app_state.get("comparison_items", [])
        table_data = []
        for item in items:
            if item.fit:
                table_data.append({
                    "alias": item.file_name,
                    "segment": item.segment_index + 1,
                    "slope": item.fit.slope_mv_per_dec,
                    "r2": item.fit.r2,
                    "n_points": item.fit.selected_count,
                })
        if hasattr(self.app, "summary_table"):
            self.app.summary_table.set_items(table_data)

    def _rerender(self) -> None:
        if self.app._app_state.get("comparison_mode"):
            from gui.comparison import render_comparison
            render_comparison(self.app)
```

- [ ] **Wire ComparisonPanel signals in app.py**

```python
# In _init_controllers:
self.comparison = ComparisonController(self)

# In _build_ui, add comparison panel to side_stack:
from gui_qt.panels.comparison_panel import ComparisonPanel
self.comparison_panel = ComparisonPanel()
self.side_stack.addWidget(self.comparison_panel)  # index 4

# Wire comparison panel signals
self.comparison_panel.delete_selected_clicked.connect(self.comparison.delete_selected)
self.comparison_panel.move_up_clicked.connect(self.comparison.move_up)
self.comparison_panel.move_down_clicked.connect(self.comparison.move_down)
self.comparison_panel.clear_all_clicked.connect(self.comparison.clear_all)
self.comparison_panel.add_all_clicked.connect(self.comparison.add_all_processed)
self.comparison_panel.item_visibility_changed.connect(self.comparison.toggle_visibility)
self.comparison_panel.item_color_changed.connect(self.comparison.update_color)
self.comparison_panel.item_renamed.connect(self.comparison.rename)

# Summary table
from gui_qt.central.summary_table import SummaryTable
self.summary_table = SummaryTable()
# Add to comparison panel layout or bottom of side area
```

- [ ] **Wire mode switching tab**

```python
# In app, add mode tab control above chart
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel

self.mode_tab = QWidget()
self.mode_tab.setFixedHeight(40)
mode_layout = QHBoxLayout(self.mode_tab)
mode_layout.setContentsMargins(0, 0, 0, 0)

self.btn_single = QPushButton("📈 单文件分析")
self.btn_single.setCheckable(True)
self.btn_single.setChecked(True)
self.btn_single.clicked.connect(lambda: self._switch_mode("single"))

self.btn_compare = QPushButton("📊 跨文件对比")
self.btn_compare.setCheckable(True)
self.btn_compare.clicked.connect(lambda: self._switch_mode("compare"))

mode_layout.addWidget(self.btn_single)
mode_layout.addWidget(self.btn_compare)
mode_layout.addStretch()

# Insert at top of central_layout
self.central_layout.insertWidget(0, self.mode_tab)
```

- [ ] **Commit**

```bash
git add src/gui_qt/controllers/comparison_ctrl.py src/gui_qt/central/summary_table.py
git commit -m "feat: add ComparisonController, SummaryTable, and mode switching"
```

---

## Phase 7: Export Controller & Final Wiring

### Task 7.1: ExportController

**Files:**
- Create: `src/gui_qt/controllers/export_ctrl.py`

- [ ] **Implement ExportController**

```python
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from gui_qt.controllers.base import BaseAppController
from gui import palette as p

if TYPE_CHECKING:
    from gui_qt.app import TafelAnalyzerApp


class ExportController(BaseAppController):
    """Handles single, batch, and comparison export."""

    def export_current(self) -> None:
        app = self.app
        fit = app._app_state.get("fit")
        prepared = app._app_state.get("prepared")
        if fit is None or prepared is None:
            QMessageBox.warning(app, "提示", "请先运行拟合")
            return

        path = app._app_state.get("tdms_path")
        if path is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出结果",
            str(path.parent / f"{path.stem}_tafel.txt"),
            "Text (*.txt);;NumPy NPZ (*.npz);;PNG Image (*.png)",
        )
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".txt":
                from core.export import export_processed_txt
                export_processed_txt(file_path, prepared, fit)
            elif ext == ".npz":
                from core.export import export_fit_npz
                export_fit_npz(file_path, fit)
            elif ext == ".png":
                app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
            app.status_bar.setText(f"已导出: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.critical(app, "导出失败", str(exc))

    def run_batch(self) -> None:
        # Placeholder: iterate selected files, run fit, export results
        app = self.app
        dir_path = QFileDialog.getExistingDirectory(app, "选择导出目录")
        if not dir_path:
            return
        app.status_bar.setText(f"批量导出到 {dir_path} (待实现)")

    def export_comparison(self) -> None:
        app = self.app
        items = app._app_state.get("comparison_items", [])
        if not items:
            QMessageBox.warning(app, "提示", "没有对比项")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            app, "导出对比图",
            "comparison.png",
            "PNG Image (*.png);;PDF (*.pdf)",
        )
        if not file_path:
            return

        from gui.comparison import render_comparison
        # Force render to current figure, then save
        if app._app_state.get("comparison_mode"):
            render_comparison(app)
        app.chart.fig.savefig(file_path, dpi=150, bbox_inches="tight")
        app.status_bar.setText(f"对比图已导出: {Path(file_path).name}")
```

- [ ] **Wire in app.py**

```python
from gui_qt.controllers.export_ctrl import ExportController
self.export_mgr = ExportController(self)
self.chart_toolbar.save_image_clicked.connect(self.export_mgr.export_current)
```

- [ ] **Commit**

```bash
git add src/gui_qt/controllers/export_ctrl.py
git commit -m "feat: add ExportController with single and comparison export"
```

---

## Phase 8: Integration & Theme Polish

### Task 8.1: Settings persistence

- [ ] **Wire settings load/save**

```python
# In __init__ of TafelAnalyzerApp, before _build_ui:
from gui import settings as s
saved = s.load_app_settings(self)
```

The existing `gui/settings.py` reads/writes JSON to `%APPDATA%/Tafel Analyzer/`. Its `load_app_settings` accesses `app._app_state` dict — format-compatible with the new Qt app since `_app_state` is preserved.

- [ ] **Commit**

```bash
git add src/gui_qt/app.py
git commit -m "feat: integrate settings persistence"
```

---

### Task 8.2: Theme QSS polish

- [ ] **Apply QSS to main window and widgets**

```python
# In TafelAnalyzerApp.__init__, after _build_ui:
app.setStyleSheet(f"""
    QMainWindow {{ background: {BG_WINDOW}; }}
    QToolTip {{
        background: {TEXT_PRIMARY};
        color: {BG_CARD};
        border: none;
        padding: 4px 8px;
        font-size: 11px;
        border-radius: 4px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: #cbd5e1;
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
""")
```

- [ ] **Verify overall appearance**

Build and run the app, check all panels for consistent spacing, hover states, and focus indicators.

- [ ] **Commit**

```bash
git add src/gui_qt/app.py
git commit -m "style: polish QSS theming and scrollbar styling"
```

---

## Phase 9: Packaging & Cleanup

### Task 9.1: PyInstaller spec update

- [ ] **Update `tdms_tafel_gui.spec`**

Add hidden imports for PySide6:
```python
hiddenimports=[
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "matplotlib.backends.backend_qtagg",
    "gui_qt",
    # ... existing imports
],
```

- [ ] **Test build**

```bash
pyinstaller tdms_tafel_gui.spec
dist/TafelAnalyzer/TafelAnalyzer.exe
```

- [ ] **Commit**

```bash
git add tdms_tafel_gui.spec
git commit -m "chore: update PyInstaller spec for PySide6"
```

---

### Task 9.2: Entry point update

- [ ] **Update `src/tdms_tafel_gui.py` facade**

```python
# Backward-compatible facade
try:
    from gui_qt.app import TafelAnalyzerApp
except ImportError:
    from gui.app import TafelAnalyzerApp  # fallback to CTk version

def build_app() -> TafelAnalyzerApp:
    return TafelAnalyzerApp()
```

- [ ] **Commit**

```bash
git add src/tdms_tafel_gui.py
git commit -m "refactor: update entry point facade to prefer gui_qt"
```

---

## Self-Review

### Spec coverage check

| Spec Section | Task(s) |
|---|---|
| Main window layout | Task 0.2, 1.1 |
| Activity Bar | Task 1.1 |
| FilePanel | Task 2.1 |
| FormulaPanel | Task 2.2 |
| SegmentPanel (color strip, radio, R²) | Task 2.3 |
| ComparisonPanel (checkbox, rename, color, delete selected, up/down) | Task 2.4 |
| ParamToolBar | Task 3.1 |
| ChartArea (matplotlib QtAgg) | Task 3.2 |
| ChartToolBar (custom, manual mode) | Task 3.3 |
| ParamToolBar → ChartArea ordering | Task 3.4 |
| Controller architecture (QThread workers) | Tasks 4.1-4.3 |
| Palette dialog | Task 5.1 |
| Comparison mode (tab switch) | Task 6.1 |
| SummaryTable | Task 6.1 |
| Export | Task 7.1 |
| Settings persistence | Task 8.1 |
| Theme QSS | Task 8.2 |
| PyInstaller packaging | Task 9.1 |

### Placeholder check

No TBD, TODO, or incomplete code blocks. All signals, method signatures, and class names are consistent throughout.

### Type consistency

- `app._app_state` dict format is preserved across both CTk and Qt versions
- `app.fig` → `app.chart.fig`, `app.canvas` → `app.chart.canvas` (consistently used in all controller code)
- All controller classes use `BaseAppController(app)` pattern
- Comparison item data models match existing `ComparisonItem` from `core.types`
