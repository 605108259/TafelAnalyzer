# Tafel Analyzer UI Redesign — PySide6 Consolidation

**Date**: 2026-04-29
**Status**: Draft
**Author**: Claude

## 1. Summary

Consolidate the PySide6 GUI's fragmented side panels, fix broken signal wiring, and complete
missing features. The goal is a working, usable application where file selection and segment
management live on a single resizable panel, operations are discoverable, and all controllers
are properly connected.

### Key changes from current gui_qt/

| Area | Current | Target |
|------|---------|--------|
| Side panels | 4 separate panels via Activity Bar | 1 primary panel (files+segments) + comparison + palette panels, 3 activity bar icons |
| File + Segment | Two separate panels | One panel with QSplitter (draggable proportion) |
| Formula + Params | FormulaPanel in sidebar; ParamToolBar above chart | Merged single toolbar above chart |
| Missing features | No multi-select, broken buttons, unwired signals | All working, matching old CTk feature set |
| Palette | Dialog or sidebar panel | Sidebar panel (320px) + full right area for color editing |

## 2. Layout

```
QMainWindow
├── QWidget — Central
    ├── QHBoxLayout
    │   ├── ActivityBar (48px fixed)
    │   ├── QStackedWidget — Side panels (320px)
    │   │   ├── FileSegmentPanel (files + segments with QSplitter)
    │   │   ├── ComparisonPanel
    │   │   └── PalettePanel (sidebar controls)
    │   └── QStackedWidget — Right area (stretch)
    │       ├── Chart workspace (toolbar + chart + chart_toolbar)
    │       └── Palette workspace (palette editing area)
```

### Activity Bar icons

| Icon | Panel | Right area |
|------|-------|------------|
| 📂 | FileSegmentPanel | Chart workspace |
| 📊 | ComparisonPanel | Chart workspace (comparison render) |
| 🎨 | PalettePanel (sidebar) | Palette workspace (right side) |

All three modes use full window width (sidebar + right area).

## 3. FileSegmentPanel (merged files + segments)

```
┌──────────────────────────────┐
│ 📂 文件 (3/18)    📁 📥 🗑 │  ← title row: count badge + icon buttons (fixed)
│ 导出名: [_________] [💾] [📦]│  ← export row: name input + export/batch buttons (fixed)
│ ┌──────────────────────────┐ │
│ │ file1.tdms     ✓      × │ │
│ │ file2.cor              × │ │  ← file QListWidget (scrollable, stretches)
│ │ ...                     │ │
│ └──────────────────────────┘ │
├──────────────────────────────┤  ← QSplitter (only lists resize; buttons/headers stay)
│ 📋 分段 (0/5) [全选][全不选][📌对比] │  ← segment header + action buttons (fixed)
│ 🎨 配色: [方案一 ▼] [应用]  [⚙]│  ← palette row (fixed)
│ ┌──────────────────────────┐ │
│ │ ▶ ☑ 第1段 (0~0.8V) 🎨 R²│ │
│ │   ☐ 第2段 (0.8~1.6V) 🎨  │ │  ← segment QListWidget (scrollable, stretches)
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

### File list widget

Each row: `fileName | ✓ badge (if processed) | × remove button`

Icon buttons (title row):
- 📁 Select files (file dialog)
- 📥 Import cache (file dialog for JSON)
- 🗑 Remove current file

Export row: export name entry + 💾 export current + 📦 batch export

### Segment list widget

Each row: `▶ (active indicator) | ☑ checkbox | segment label | R² badge | 🎨 color swatch`

Action buttons:
- 全选 / 全不选 — toggle checkboxes
- 📌 加入对比 — add selected segments to comparison

Palette row: scheme dropdown + apply button + manage button (opens palette panel)

### QSplitter behavior

Only the two QListWidgets participate in the splitter. Title rows, button rows, export row,
palette row are all outside the splitter and remain fixed height.

## 4. Toolbar (formula + params + fit operations)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 电压公式: [                  ]  电流公式: [                     ]    │
│ E_eq: [    ] 窗口: [    ] η: [    ] logj: [    ] R²: [   ] 优先: [▼]│
│                                    [▶ 拟合] [🖱 手动]               │
└──────────────────────────────────────────────────────────────────────┘
```

Two rows, fixed height. Replaces FormulaPanel + ParamToolBar.
Fit button runs auto-fitting. Manual button activates RectangleSelector on chart.

## 5. ComparisonPanel

```
┌──────────────────────────────┐
│ 📊 对比  [📥添加] [🗑删除] [↑] [↓] [🗑清空] [💾导出] │
│ 🎨 配色: [方案一 ▼] [应用] [⚙]│
│ ┌──────────────────────────┐ │
│ │ ☑ file1-第1段       🎨  │ │
│ │ ☑ file2-第2段       🎨  │ │
│ └──────────────────────────┘ │
│ ┌──────────────────────────┐ │
│ │      汇总结果文本          │ │
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

All operation buttons in the header row. Each item row:
- QCheckBox (visibility toggle)
- QLineEdit (double-click to rename)
- segment label
- color swatch (click → QColorDialog)

Matches old CTk comparison feature set exactly.

## 6. Palette Management

Left sidebar (320px):
```
┌──────────────────────────────┐
│ 🎨 配色方案                  │
│ ┌──────────────────────────┐ │
│ │ [方案一 ▼]               │ │  ← QComboBox
│ └──────────────────────────┘ │
│ 色阶预览                     │
│ ┌──────────────────────────┐ │
│ │ ■■■■■■■■■■              │ │  ← gradient preview
│ └──────────────────────────┘ │
│ ┌──────────────────────────┐ │
│ │ ■  #b90746   第1段       │ │
│ │ ■  #0891b2   第2段       │ │  ← color list (swatch + hex + segment name)
│ │ ■  #7c3aed   第3段       │ │
│ └──────────────────────────┘ │
│ 颜色数: [▼ 5 6 8 10 12 16]  │
│ [应用到当前] [另存为新方案]   │
│ [🗑 删除方案]                 │
└──────────────────────────────┘
```

Right area: large color grid and preview. Shows the active scheme's colors as a grid
of large swatches with hex codes. Each swatch is clickable to change color via
QColorDialog. The layout mirrors Origin's color map editor — swatches arranged in
rows, with the scheme gradient preview at top.

## 7. Chart Toolbar (matplotlib navigation)

Below chart, fixed height:
`[🏠 复位] [←] [→] [🔍+] [🔍-] [✋ 平移] [💾 保存图片]`

## 8. File Changes

```
NEW:     src/gui_qt/panels/file_segment.py    — merged file + segment panel
NEW:     src/gui_qt/central/toolbar.py          — formula + params merged toolbar
NEW:     src/gui_qt/central/palette_workspace.py — right-side palette editor (placeholder)
MODIFY:  src/gui_qt/app.py                      — rebuild _build_ui + _init_controllers
MODIFY:  src/gui_qt/activity_bar.py             — 3 icons (file/compare/palette)
MODIFY:  src/gui_qt/panels/comparison.py        — fix signals, add missing buttons
MODIFY:  src/gui_qt/panels/palette.py           — new panel (left sidebar)
MODIFY:  src/gui_qt/central/chart_toolbar.py    — add manual fit, zoom controls
MODIFY:  src/gui_qt/theme.py                    — add new component styles
MODIFY:  src/gui_qt/controllers/file_ctrl.py    — adapt to merged panel
MODIFY:  src/gui_qt/controllers/fitting_ctrl.py — adapt to merged toolbar
MODIFY:  src/gui_qt/controllers/comparison_ctrl.py — complete wiring
MODIFY:  src/gui_qt/controllers/export_ctrl.py  — complete wiring
DELETE:  src/gui_qt/panels/formula_panel.py     — merged into toolbar
DELETE:  src/gui_qt/central/param_bar.py        — merged into toolbar
```

## 9. Implementation Order

1. Build `FileSegmentPanel` with QSplitter (file list + segment list)
2. Build `Toolbar` (formula + params, placed above chart)
3. Rebuild `app.py` layout with new panels + 3-icon activity bar
4. Fix `ComparisonPanel` (buttons, signals, layout)
5. Build `PalettePanel` sidebar + placeholder right workspace
6. Wire all controllers (file, fitting, comparison, export)
7. Polish chart toolbar
8. Test full workflow: load → fit → export → compare

## 10. Out of Scope

- core/ module changes
- Dark mode
- CI/CD
- PyInstaller updates
