# Tkinter 清理与目录重组设计

## Context

项目已完成从 CustomTkinter 到 PySide6 的功能迁移（`gui_qt/`），但旧的 `src/gui/` 目录仍包含 10 个 tkinter 专属文件和 6 个被 Qt 代码依赖的共享模块。本次清理目标：
- 删除所有 tkinter 相关代码
- 将共享模块迁移到 `core/`
- 将 `gui_qt/` 重命名为 `ui/`

## 最终目录结构

```
src/
├── core/                # 纯业务逻辑 + 迁入的共享模块
│   ├── types.py, readers.py, formula.py, fitting.py, export.py, cli.py, utils.py  (不变)
│   ├── theme.py         ← gui/theme.py
│   ├── rendering.py     ← gui/rendering.py (清理 tkinter 死代码)
│   ├── comparison.py    ← gui/comparison.py
│   ├── serialization.py ← gui/serialization.py
│   ├── cache.py         ← gui/cache.py
│   └── logger.py        ← gui/logger.py
├── ui/                  ← gui_qt/ (重命名)
│   ├── app.py, activity_bar.py, theme.py, icons.py, settings.py
│   ├── controllers/
│   ├── panels/
│   └── central/
└── scripts/
    └── verify_refactor.py  (删除)
```

## 实施步骤

### Step 1: 删除 tkinter 专属文件 (10 files)

| 文件 | 原因 |
|------|------|
| `src/gui/__init__.py` | re-exports CTk app |
| `src/gui/app.py` | CTk 主窗口，imports customtkinter/tkinterdnd2 |
| `src/gui/app_builder.py` | CTk UI 构建，imports FigureCanvasTkAgg |
| `src/gui/widgets.py` | CTk widget 工厂 |
| `src/gui/tooltip.py` | tkinter tooltip widget |
| `src/gui/palette.py` | tkinter colorchooser/messagebox |
| `src/gui/settings.py` | 依赖 CTk widget methods（gui_qt/settings.py 已有替代） |
| `src/gui/controllers/__init__.py` | 空包 |
| `src/gui/controllers/*.py` (5) | 全部 CTk 控制器 |

### Step 2: 迁移共享模块到 core/ (6 files)

| 源路径 | 目标路径 | tkinter 依赖 |
|--------|----------|-------------|
| `gui/theme.py` | `core/theme.py` | 无 |
| `gui/rendering.py` | `core/rendering.py` | 需清理（见 Step 3） |
| `gui/comparison.py` | `core/comparison.py` | 无直接依赖 |
| `gui/serialization.py` | `core/serialization.py` | 无 |
| `gui/cache.py` | `core/cache.py` | 无（内部引用 gui.rendering/gui.serialization 需更新） |
| `gui/logger.py` | `core/logger.py` | 无 |

### Step 3: 清理共享模块中的 tkinter 死代码

**`rendering.py` 迁移后需修改：**
- 删除 `clear_toolbar_mode()` 函数（含 `get_tk_widget` tkinter 代码，Qt 不需要）
- TYPE_CHECKING: `from gui.app import TafelAnalyzerApp` → `from ui.app import TafelAnalyzerApp`
- 内部 `from gui.theme` → `from core.theme`

**`comparison.py` 迁移后需修改：**
- TYPE_CHECKING: `from gui.app` → `from ui.app`
- 内部 `from gui.theme` → `from core.theme`，`from gui.rendering` → `from core.rendering`

**`cache.py` 迁移后需修改：**
- TYPE_CHECKING: `from gui.app` → `from ui.app`
- 内部 `from gui.serialization` → `from core.serialization`，`from gui.rendering` → `from core.rendering`

### Step 4: 重命名 gui_qt/ → ui/

使用 `git mv src/gui_qt src/ui`

### Step 5: 更新 ui/ 内所有导入

| 原导入 | 新导入 | 涉及文件数 |
|--------|--------|-----------|
| `from gui.rendering import ...` | `from core.rendering import ...` | ~8 处 (fitting_ctrl.py, file_ctrl.py) |
| `from gui.comparison import ...` | `from core.comparison import ...` | ~4 处 (comparison_ctrl.py, export_ctrl.py, file_ctrl.py) |
| `from gui.serialization import ...` | `from core.serialization import ...` | 1 处 (file_ctrl.py) |
| `from gui.cache import ...` | `from core.cache import ...` | 如存在 |

### Step 6: 删除遗留文件

- `src/tdms_tafel_gui.py` — backward-compatibility facade，无任何模块导入它
- `src/gui/` 目录（Step 2 迁移后应为空）
- `src/scripts/verify_refactor.py` — 仅检查 tkinter 时代的 gui/ 包

### Step 7: 更新入口和文档

- `main.py`: `from gui_qt.app` → `from ui.app`
- `CLAUDE.md`: 删除 tkinter 引用，更新目录结构

## 验证

1. `python -c "from ui.app import TafelAnalyzerApp"` — 导入成功
2. `python main.py` — GUI 正常启动
3. 全局搜索确认无 `import tkinter`、`import customtkinter`、`from gui.` 残留
4. `git status` 确认所有变更在预期范围内
