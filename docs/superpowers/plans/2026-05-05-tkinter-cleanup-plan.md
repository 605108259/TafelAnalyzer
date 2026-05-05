# Tkinter 清理与目录重组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除所有 tkinter 相关代码，将共享模块迁移到 core/，将 gui_qt/ 重命名为 ui/

**Architecture:** 分 7 个原子任务：先删 tkinter 专属文件，再迁移共享模块到 core/ 并清理死代码，然后重命名 gui_qt/ 为 ui/ 并更新所有导入，最后清理遗留文件和文档。

**Tech Stack:** Python, PySide6, matplotlib, git

---

## File Map

本次操作涉及的文件一览：

| 操作 | 文件 | 说明 |
|------|------|------|
| DELETE | `src/gui/__init__.py` | re-exports CTk app |
| DELETE | `src/gui/app.py` | CTk 主窗口 |
| DELETE | `src/gui/app_builder.py` | CTk UI 构建 |
| DELETE | `src/gui/widgets.py` | CTk widget 工厂 |
| DELETE | `src/gui/tooltip.py` | tkinter tooltip |
| DELETE | `src/gui/palette.py` | tkinter palette |
| DELETE | `src/gui/settings.py` | CTk settings (gui_qt 版已存在) |
| DELETE | `src/gui/controllers/__init__.py` | 空包 |
| DELETE | `src/gui/controllers/comparison_mgr.py` | CTk controller |
| DELETE | `src/gui/controllers/export_mgr.py` | CTk controller |
| DELETE | `src/gui/controllers/file_mgr.py` | CTk controller |
| DELETE | `src/gui/controllers/fitting_ctrl.py` | CTk controller |
| DELETE | `src/gui/controllers/segment_panel.py` | CTk controller |
| MOVE | `src/gui/theme.py` → `src/core/theme.py` | 颜色/样式常量 |
| MOVE+EDIT | `src/gui/rendering.py` → `src/core/rendering.py` | matplotlib 渲染（清理死代码） |
| MOVE+EDIT | `src/gui/comparison.py` → `src/core/comparison.py` | 对比渲染 |
| MOVE | `src/gui/serialization.py` → `src/core/serialization.py` | 数据序列化 |
| MOVE+EDIT | `src/gui/cache.py` → `src/core/cache.py` | 缓存逻辑 |
| MOVE | `src/gui/logger.py` → `src/core/logger.py` | 日志 |
| RENAME | `src/gui_qt/` → `src/ui/` | 整个 Qt 包 |
| EDIT | `src/ui/__init__.py` | 更新导入 |
| EDIT | `src/ui/app.py` | 更新 ~20 处 gui_qt → ui 导入 |
| EDIT | `src/ui/activity_bar.py` | 更新 1 处导入 |
| EDIT | `src/ui/settings.py` | 更新 1 处导入 |
| EDIT | `src/ui/controllers/base.py` | 更新 1 处导入 |
| EDIT | `src/ui/controllers/file_ctrl.py` | 更新 gui_qt→ui 和 gui→core 导入 |
| EDIT | `src/ui/controllers/fitting_ctrl.py` | 更新 gui_qt→ui 和 gui→core 导入 |
| EDIT | `src/ui/controllers/comparison_ctrl.py` | 更新 gui_qt→ui 和 gui→core 导入 |
| EDIT | `src/ui/controllers/export_ctrl.py` | 更新 gui_qt→ui 和 gui→core 导入 |
| EDIT | `src/ui/panels/file_segment.py` | 更新 2 处导入 |
| EDIT | `src/ui/panels/comparison.py` | 更新 2 处导入 |
| EDIT | `src/ui/panels/palette.py` | 更新 1 处导入 |
| EDIT | `src/ui/central/toolbar.py` | 更新 2 处导入 |
| EDIT | `src/ui/central/chart_widget.py` | 更新 1 处导入 |
| EDIT | `src/ui/central/chart_toolbar.py` | 更新 2 处导入 |
| EDIT | `src/ui/central/palette_workspace.py` | 更新 1 处导入 |
| DELETE | `src/tdms_tafel_gui.py` | 遗留 facade |
| DELETE | `src/scripts/verify_refactor.py` | tkinter 时代的验证脚本 |
| EDIT | `main.py` | 更新导入 |
| EDIT | `CLAUDE.md` | 删除 tkinter 引用 |

---

## Task 1: 删除 tkinter 专属文件

**Files:** 10 files to delete

- [ ] **Step 1.1: 删除 `src/gui/controllers/` 整个目录（5 个 .py 文件 + __init__.py）**

```bash
git rm src/gui/controllers/__init__.py
git rm src/gui/controllers/comparison_mgr.py
git rm src/gui/controllers/export_mgr.py
git rm src/gui/controllers/file_mgr.py
git rm src/gui/controllers/fitting_ctrl.py
git rm src/gui/controllers/segment_panel.py
```

- [ ] **Step 1.2: 删除 `src/gui/` 下的 tkinter 专属文件**

```bash
git rm src/gui/__init__.py
git rm src/gui/app.py
git rm src/gui/app_builder.py
git rm src/gui/widgets.py
git rm src/gui/tooltip.py
git rm src/gui/palette.py
git rm src/gui/settings.py
```

- [ ] **Step 1.3: 验证 — 确认 gui/ 下只剩共享模块**

Run: `ls src/gui/`
Expected: `cache.py  comparison.py  logger.py  rendering.py  serialization.py  theme.py`

- [ ] **Step 1.4: 提交**

```bash
git add -A
git commit -m "refactor: remove 10 tkinter-only files from gui/"
```

## Task 2: 迁移共享模块到 core/

**Files:** 6 files to move from `src/gui/` to `src/core/`

- [ ] **Step 2.1: 移动 6 个文件**

```bash
git mv src/gui/theme.py src/core/theme.py
git mv src/gui/rendering.py src/core/rendering.py
git mv src/gui/comparison.py src/core/comparison.py
git mv src/gui/serialization.py src/core/serialization.py
git mv src/gui/cache.py src/core/cache.py
git mv src/gui/logger.py src/core/logger.py
```

- [ ] **Step 2.2: 验证 — `src/gui/` 目录应为空**

Run: `ls src/gui/ 2>/dev/null || echo "directory empty or gone"`
Expected: `directory empty or gone` 或空输出

- [ ] **Step 2.3: 提交**

```bash
git add -A
git commit -m "refactor: move 6 shared modules from gui/ to core/"
```

## Task 3: 清理迁移后的共享模块中的 tkinter 死代码

**Files:** `src/core/rendering.py`, `src/core/comparison.py`, `src/core/cache.py`

- [ ] **Step 3.1: 编辑 `src/core/rendering.py` — 删除 `clear_toolbar_mode()` 函数**

该函数使用 `get_tk_widget` (tkinter 特有)，Qt 不需要。删除第 17-25 行（含）：

```python
# 删除这段代码:
def clear_toolbar_mode(app: TafelAnalyzerApp) -> None:
    mode_text = str(getattr(app.toolbar, "mode", "")).lower()
    if "zoom" in mode_text:
        app.toolbar.zoom()
    elif "pan" in mode_text:
        app.toolbar.pan()
    canvas_widget = getattr(app.canvas, "get_tk_widget", None)
    if callable(canvas_widget):
        canvas_widget().focus_set()
```

- [ ] **Step 3.2: 编辑 `src/core/rendering.py` — 更新 TYPE_CHECKING 导入**

将第 14 行:
```python
from gui.app import TafelAnalyzerApp
```
改为:
```python
from ui.app import TafelAnalyzerApp
```

- [ ] **Step 3.3: 编辑 `src/core/rendering.py` — 更新内部 `from gui.theme` 导入**

全局替换 `from gui.theme` → `from core.theme`（出现在第 76 行和第 400 行）:

```python
# line 76
from core.theme import MPL_RC, TEXT_PRIMARY

# line 400
from core.theme import MPL_RC, TEXT_SECONDARY
```

- [ ] **Step 3.4: 编辑 `src/core/comparison.py` — 更新 TYPE_CHECKING 导入**

将第 12 行:
```python
from gui.app import TafelAnalyzerApp
```
改为:
```python
from ui.app import TafelAnalyzerApp
```

- [ ] **Step 3.5: 编辑 `src/core/comparison.py` — 更新内部导入**

将第 45 行:
```python
from gui.theme import MPL_RC, TEXT_PRIMARY
```
改为:
```python
from core.theme import MPL_RC, TEXT_PRIMARY
```

将第 46-50 行:
```python
from gui.rendering import (
    apply_plot_view_state,
    capture_plot_view_state,
    enable_draggable_legend,
)
```
改为:
```python
from core.rendering import (
    apply_plot_view_state,
    capture_plot_view_state,
    enable_draggable_legend,
)
```

- [ ] **Step 3.6: 编辑 `src/core/cache.py` — 更新 TYPE_CHECKING 导入**

将第 12 行:
```python
from gui.app import TafelAnalyzerApp
```
改为:
```python
from ui.app import TafelAnalyzerApp
```

- [ ] **Step 3.7: 编辑 `src/core/cache.py` — 更新内部导入**

将第 9 行:
```python
from gui.serialization import fit_to_dict, prepared_to_dict
```
改为:
```python
from core.serialization import fit_to_dict, prepared_to_dict
```

将第 67 行:
```python
from gui.rendering import capture_axes_limits, capture_plot_view_state
```
改为:
```python
from core.rendering import capture_axes_limits, capture_plot_view_state
```

- [ ] **Step 3.8: 提交**

```bash
git add -A
git commit -m "refactor: clean tkinter dead code from shared modules"
```

## Task 4: 重命名 gui_qt/ 为 ui/

**Files:** 整个 `src/gui_qt/` 目录

- [ ] **Step 4.1: 执行重命名**

```bash
git mv src/gui_qt src/ui
```

- [ ] **Step 4.2: 提交**

```bash
git add -A
git commit -m "refactor: rename gui_qt/ to ui/"
```

## Task 5: 更新 ui/ 包内所有导入

**Files:** `src/ui/` 下 16 个 Python 文件

需要两类替换：
1. `gui_qt.` → `ui.`（包内互相引用，~30 处）
2. `gui.` → `core.`（引用已迁移的共享模块，~14 处）

- [ ] **Step 5.1: 编辑 `src/ui/__init__.py`**

将:
```python
from gui_qt.app import TafelAnalyzerApp
```
改为:
```python
from ui.app import TafelAnalyzerApp
```

- [ ] **Step 5.2: 编辑 `src/ui/app.py` — 替换所有 `gui_qt.` → `ui.`**

第 8 行: `from gui_qt.activity_bar` → `from ui.activity_bar`
第 9 行: `from gui_qt.theme` → `from ui.theme`
第 84 行: `from gui_qt.settings` → `from ui.settings`
第 148 行: `from gui_qt.panels.file_segment` → `from ui.panels.file_segment`
第 149 行: `from gui_qt.panels.comparison` → `from ui.panels.comparison`
第 150 行: `from gui_qt.panels.palette` → `from ui.panels.palette`
第 172 行: `from gui_qt.central.toolbar` → `from ui.central.toolbar`
第 173 行: `from gui_qt.central.chart_widget` → `from ui.central.chart_widget`
第 174 行: `from gui_qt.central.summary_table` → `from ui.central.summary_table`
第 183 行: `from gui_qt.theme` → `from ui.theme`
第 184 行: `from gui_qt.icons` → `from ui.icons`
第 234 行: `from gui_qt.central.palette_workspace` → `from ui.central.palette_workspace`
第 314 行: `from gui_qt.controllers.file_ctrl` → `from ui.controllers.file_ctrl`
第 315 行: `from gui_qt.controllers.fitting_ctrl` → `from ui.controllers.fitting_ctrl`
第 316 行: `from gui_qt.controllers.comparison_ctrl` → `from ui.controllers.comparison_ctrl`
第 317 行: `from gui_qt.controllers.export_ctrl` → `from ui.controllers.export_ctrl`

- [ ] **Step 5.3: 编辑 `src/ui/activity_bar.py`**

第 8 行: `from gui_qt.theme` → `from ui.theme`

- [ ] **Step 5.4: 编辑 `src/ui/settings.py`**

第 13 行: `from gui_qt.app` → `from ui.app`

- [ ] **Step 5.5: 编辑 `src/ui/controllers/base.py`**

第 8 行: `from gui_qt.app` → `from ui.app`

- [ ] **Step 5.6: 编辑 `src/ui/controllers/file_ctrl.py`**

替换所有导入：
- 第 15 行: `from gui_qt.controllers.base` → `from ui.controllers.base`
- 第 18 行: `from gui_qt.app` → `from ui.app`
- 第 270 行: `from gui.serialization` → `from core.serialization`
- 第 272 行: `from gui import cache as c` → `from core import cache as c`
- 第 343 行: `from gui.comparison` → `from core.comparison`
- 第 433 行: `from gui.rendering` → `from core.rendering`

- [ ] **Step 5.7: 编辑 `src/ui/controllers/fitting_ctrl.py`**

替换所有导入：
- 第 10 行: `from gui_qt.controllers.base` → `from ui.controllers.base`
- 第 13 行: `from gui_qt.app` → `from ui.app`
- 第 228 行: `from gui.rendering` → `from core.rendering`
- 第 263 行: `from gui.rendering` → `from core.rendering`
- 第 273 行: `from gui.rendering` → `from core.rendering`
- 第 287 行: `from gui.rendering` → `from core.rendering`
- 第 329 行: `from gui.rendering` → `from core.rendering`

- [ ] **Step 5.8: 编辑 `src/ui/controllers/comparison_ctrl.py`**

替换所有导入：
- 第 8 行: `from gui_qt.controllers.base` → `from ui.controllers.base`
- 第 9 行: `from gui import comparison as comp` → `from core import comparison as comp`
- 第 12 行: `from gui_qt.app` → `from ui.app`
- 第 187 行: `from gui.comparison` → `from core.comparison`

- [ ] **Step 5.9: 编辑 `src/ui/controllers/export_ctrl.py`**

替换所有导入：
- 第 9 行: `from gui_qt.controllers.base` → `from ui.controllers.base`
- 第 12 行: `from gui_qt.app` → `from ui.app`
- 第 164 行: `from gui.comparison` → `from core.comparison`

- [ ] **Step 5.10: 编辑 `src/ui/panels/file_segment.py`**

- 第 12 行: `from gui_qt.theme` → `from ui.theme`
- 第 18 行: `from gui_qt.icons` → `from ui.icons`

- [ ] **Step 5.11: 编辑 `src/ui/panels/comparison.py`**

- 第 10 行: `from gui_qt.theme` → `from ui.theme`
- 第 15 行: `from gui_qt.icons` → `from ui.icons`

- [ ] **Step 5.12: 编辑 `src/ui/panels/palette.py`**

- 第 9 行: `from gui_qt.theme` → `from ui.theme`

- [ ] **Step 5.13: 编辑 `src/ui/central/toolbar.py`**

- 第 9 行: `from gui_qt.theme` → `from ui.theme`
- 第 38 行: `from gui_qt.icons` → `from ui.icons`

- [ ] **Step 5.14: 编辑 `src/ui/central/chart_widget.py`**

- 第 12 行: `from gui_qt.theme` → `from ui.theme`

- [ ] **Step 5.15: 编辑 `src/ui/central/chart_toolbar.py`**

- 第 6 行: `from gui_qt.theme` → `from ui.theme`
- 第 9 行: `from gui_qt.central.chart_widget` → `from ui.central.chart_widget`

- [ ] **Step 5.16: 编辑 `src/ui/central/palette_workspace.py`**

- 第 6 行: `from gui_qt.theme` → `from ui.theme`

- [ ] **Step 5.17: 提交**

```bash
git add -A
git commit -m "refactor: update all imports from gui_qt to ui and gui to core"
```

## Task 6: 删除遗留文件

**Files:** `src/tdms_tafel_gui.py`, `src/scripts/verify_refactor.py`, 空目录 `src/gui/`

- [ ] **Step 6.1: 删除 `src/tdms_tafel_gui.py`**

```bash
git rm src/tdms_tafel_gui.py
```

- [ ] **Step 6.2: 删除 `src/scripts/verify_refactor.py` 及空的 `src/scripts/` 目录**

```bash
git rm src/scripts/verify_refactor.py
rmdir src/scripts
```

- [ ] **Step 6.3: 删除空的 `src/gui/` 目录**

```bash
rmdir src/gui 2>/dev/null || true
```

- [ ] **Step 6.4: 全局搜索确认无残留**

Run:
```bash
grep -rn "import tkinter\|import customtkinter\|from gui\.\|from gui_qt\.\|from gui import" src/
```
Expected: 无匹配结果

- [ ] **Step 6.5: 提交**

```bash
git add -A
git commit -m "refactor: remove legacy facade, verify script, and empty gui/ directory"
```

## Task 7: 更新入口文件和文档

**Files:** `main.py`, `CLAUDE.md`

- [ ] **Step 7.1: 编辑 `main.py`**

将:
```python
from gui_qt.app import TafelAnalyzerApp
```
改为:
```python
from ui.app import TafelAnalyzerApp
```

- [ ] **Step 7.2: 编辑 `CLAUDE.md` — 删除 Section 2 (Legacy CustomTkinter)**

删除第 41-43 行：
```
### 2. `src/gui/` — Legacy CustomTkinter GUI (being replaced)
- Full app with TkinterDnD2 drag-drop, CTk widgets, matplotlib TkAgg
- Controllers in `src/gui/controllers/` (FileManager, FittingController, ExportManager, ComparisonManager, SegmentPanel)
```

- [ ] **Step 7.3: 编辑 `CLAUDE.md` — 重编号 Section 3 为 Section 2，更新标题**

将:
```
### 3. `src/gui_qt/` — New PySide6 GUI (active migration)
```
改为:
```
### 2. `src/ui/` — PySide6 GUI
```

同时将 `gui_qt` 相关路径更新为 `ui`。

- [ ] **Step 7.4: 编辑 `CLAUDE.md` — 更新 Project Overview**

将:
```
Currently migrating from CustomTkinter to PySide6.
```
改为:
```
Built with PySide6 (Qt).
```

- [ ] **Step 7.5: 编辑 `CLAUDE.md` — 更新 Key patterns 中的 Migration status**

删除:
```
- **Migration status**: `gui_qt` is replacing `gui`. Recent commits show progressive migrating of controllers, panels, and removing old modules.
- **matplotlib backend**: `QtAgg` for PySide6, `TkAgg` in legacy
```
改为:
```
- **matplotlib backend**: `QtAgg` (PySide6)
```

- [ ] **Step 7.6: 编辑 `CLAUDE.md` — 更新 Project Structure 目录树**

替换为：
```
src/
├── core/              # Pure logic + shared rendering/utilities
│   ├── types.py       # Data classes & constants
│   ├── readers.py     # File I/O
│   ├── formula.py     # Formula parsing
│   ├── fitting.py     # Tafel fitting
│   ├── export.py      # Export & plotting
│   ├── cli.py         # CLI
│   ├── utils.py       # Utilities
│   ├── theme.py       # Color/style constants
│   ├── rendering.py   # Matplotlib chart rendering
│   ├── comparison.py  # Comparison chart rendering
│   ├── serialization.py # Data serialization
│   ├── cache.py       # Result caching
│   └── logger.py      # Application logging
├── ui/                # PySide6 GUI
│   ├── controllers/
│   ├── panels/
│   └── central/
main.py                # GUI entry point
run_cli.py             # CLI entry point
TafelAnalyzer_Setup.iss # Inno Setup installer config
data/                  # Sample .tdms files
```

- [ ] **Step 7.7: 编辑 `CLAUDE.md` — 删除 verify_refactor 相关内容**

删除:
```
- **Verify script**: Run `src/scripts/verify_refactor.py` after refactoring to catch parameter mismatches and stale app attribute references
```

同时删除 Commands 中的:
```
# Run refactoring verification (checks cross-module consistency during migration)
python src/scripts/verify_refactor.py
```

- [ ] **Step 7.8: 更新 Important constraints 中的 Migration 引用**

将:
```
- **In-place migration**: `gui_qt/` depends on `core/` (same as `gui/`) — no duplication of core logic
```
改为:
```
- **Layered architecture**: `ui/` depends on `core/` — no duplication of logic
```

- [ ] **Step 7.9: 提交**

```bash
git add -A
git commit -m "docs: update main.py and CLAUDE.md to reflect tkinter removal"
```

## 验证

- [ ] **Step 8.1: 导入验证**

```bash
python -c "from ui.app import TafelAnalyzerApp; print('OK')"
```
Expected: `OK`

- [ ] **Step 8.2: 全局无残留搜索**

```bash
grep -rn "import tkinter\|import customtkinter\|from gui\.\|from gui_qt\.\|from gui import" src/ || echo "CLEAN"
```
Expected: `CLEAN`

- [ ] **Step 8.3: 目录结构检查**

```bash
ls src/
```
Expected: `core/  ui/`

- [ ] **Step 8.4: git 状态确认**

```bash
git status
```
Expected: clean working tree
