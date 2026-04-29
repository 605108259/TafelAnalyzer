# Tafel Analyzer UI Redesign — PySide6 Migration

**Date**: 2026-04-29
**Status**: Draft
**Author**: Claude

## 1. Executive Summary

Migrate Tafel Analyzer's GUI from CustomTkinter to PySide6 (Qt for Python) to achieve a modern consumer-app-quality interface while preserving the existing `core/` computation layer intact. The new UI follows VS Code / Notion design language in light mode, with a collapsible activity bar, stackable side panels, a top-mounted parameter toolbar above the matplotlib chart area, and a streamlined comparison mode.

---

## 2. Architecture

### Technology Stack

| Layer | Current | Target |
|-------|---------|--------|
| GUI framework | CustomTkinter (Tkinter) | PySide6 (Qt 6) |
| Charting | matplotlib TkAgg | matplotlib QtAgg |
| Packaging | PyInstaller + InnoSetup | PyInstaller + InnoSetup (unchanged) |
| Compute | `core/` (numpy) | `core/` (unchanged) |

### `core/` preservation

All modules under `src/core/` (types, readers, fitting, formula, export, cli, utils) remain completely unchanged. The migration is strictly a `src/gui/` replacement.

### Layout hierarchy (QMainWindow)

```
QMainWindow
├── QMenuBar (File / Edit / View / Help)
├── QSplitter (horizontal, draggable divider)
│   ├── QWidget — Activity Bar (fixed 48px, icon buttons)
│   ├── QStackedWidget — Side Panels (default 320px, collapsible)
│   │   ├── FilePanel (file selection, recent files, cache import)
│   │   ├── FormulaPanel (potential/current formula, channel list)
│   │   ├── SegmentPanel (segment list with checkboxes, color indicators)
│   │   └── ComparisonPanel (comparison items, only shown in compare mode)
│   └── QWidget — Central Area (stretch)
│       ├── ParamToolBar (fixed height, E_eq / window / R² / Run button)
│       ├── matplotlib FigureCanvasQTAgg (stretch, dual plots)
│       ├── ChartToolBar (fixed height, zoom/pan/home/export controls)
│       └── StatusBar (single-line status text)
```

### Signal/Slot architecture

- `core/` computation runs in `QThread` workers
- Each worker emits `finished(result)` signal back to main thread
- Generation counter (`_op_generation`) preserved to discard stale results
- UI components connect via typed signals, not raw `app.after()` callbacks

---

## 3. Window Structure & Navigation

### Activity Bar (48px left column)

Fixed-width vertical button strip. Icons with tooltips:

| Icon | Panel | Tooltip |
|------|-------|---------|
| 📂 | FilePanel | Files |
| 📐 | FormulaPanel | Formulas |
| 📋 | SegmentPanel | Segments |
| ⚙ | (none — toggles ParamToolBar visibility) | Parameters |

Interaction:
- Click icon → show corresponding panel in QStackedWidget
- Click same icon again → collapse side panel (chart expands to fill space)
- Active icon highlighted with accent color left border

### Side Panels (320px default, resizable via QSplitter)

Each panel is a `QWidget` subclass with a title label and scrollable content area. Panels share no persistent state; they read/write through the app controller layer.

---

## 4. Side Panels

### 4.1 FilePanel

```
┌─────────────────────────┐
│ 📂 文件                  │
│                         │
│ [📁 选择数据文件…]        │ ← QPushButton, accent
│                         │
│ ┌─────────────────────┐ │
│ │ data1.tdms  ✓     × │ │ ← QListWidget items
│ │ data2.tdms  ✓     × │ │   each with custom widget:
│ │ data3.txt         × │ │   - filename label
│ │ data4.cor        × │ │   - "✓" processed badge (green)
│ └─────────────────────┘ │   - "×" remove button
│                         │
│ [📥 导入缓存]            │
│                         │
│ 5 channels · 3 segments │ ← info label
└─────────────────────────┘
```

- Drag-and-drop from file manager (native Qt DnD)
- Double-click to switch file
- Remove button prompts confirmation dialog

### 4.2 FormulaPanel

```
┌─────────────────────────┐
│ 📐 公式                  │
│                         │
│ 电压公式:                │
│ ┌─────────────────────┐ │
│ │ -[Vgs] + 0.23      │ │ ← QLineEdit
│ └─────────────────────┘ │
│ 电流公式:                │
│ ┌─────────────────────┐ │
│ │ [Igs] / area       │ │ ← QLineEdit
│ └─────────────────────┘ │
│                         │
│ [应用公式并拟合]          │ ← single combined action
│                         │
│ 可用 Channel:            │
│ ┌─────────────────────┐ │
│ │ Vgs  Igs  Vds      │ │ ← QTextBrowser, read-only
│ │ Temp  Area          │ │   click to insert at cursor
│ └─────────────────────┘ │
└─────────────────────────┘
```

- Channel names are clickable: clicking inserts `[ChannelName]` at cursor position in the active formula field
- Formula validation happens inline with red border on error
- Errors shown below the input in a small red QLabel

### 4.3 SegmentPanel

```
┌─────────────────────────┐
│ 📋 分段                  │
│                         │
│ [全选] [全不选]           │
│                         │
│ ┌─────────────────────┐ │
│ │ ◉ 第1段  R²=0.997  │ │ ← active (filled circle)
│ │   sample_1.tdms     │ │   color bar on left (8px)
│ │─────────────────────│ │
│ │ ○ 第2段  R²=0.992  │ │ ← inactive (outline circle)
│ │   sample_1.tdms     │ │
│ │─────────────────────│ │
│ │ ○ 第3段  — 未拟合   │ │ ← unfitted (gray, no R²)
│ │   sample_1.tdms     │ │
│ └─────────────────────┘ │
│                         │
│ [📌 添加到对比]           │
└─────────────────────────┘
```

- Custom `QListWidget` with delegate rendering each segment as a compact card
- Left color strip (8px wide QFrame) for visual segment identification
- Radio-button-style circle indicates active segment
- Right side shows fit quality (R² or "未拟合")
- Double-click color strip → QColorDialog to change segment color

### 4.4 ComparisonPanel

```
┌─────────────────────────┐
│ 📊 对比                  │
│                         │
│ [🗑 删除选中] [↑] [↓]    │ ← top action bar
│                         │
│ ┌─────────────────────┐ │
│ │ ☑ sample_1-第1段 ⬤ │ │ ← checked = visible
│ │ ☐ 我的对照样-第3段 ⬤ │ │ ← unchecked = hidden
│ │ ☑ sample_3-第1段 ⬤ │ │
│ └─────────────────────┘ │
│                         │
│ [📥 添加所有已处理]       │
│ [🗑 清空全部]            │
└─────────────────────────┘
```

- Each row is a custom QWidget:
  - **☑ checkbox** — toggle visibility in chart
  - **filename QLineEdit** — borderless, double-click to edit, Enter to confirm
  - **-第N段 QLabel** — read-only segment index
  - **⬤ QPushButton** — circular color swatch, click opens QColorDialog
- Click on row (not checkbox) → select/highlight it
- **删除选中** removes the highlighted row
- **↑/↓** reorder selected item
- Drag-and-drop reorder also supported

---

## 5. Central Area

### 5.1 ParamToolBar

```
┌──────────────────────────────────────────────────────────────┐
│  E_eq: [0    ]  窗口: [12-15]  η: [      ]  logj: [      ]  │
│  R²: [0.95 ]  优先: [斜率 ▼]               [▶ 自动拟合     ]│
└──────────────────────────────────────────────────────────────┘
```

- Horizontal layout, fixed height (~44px)
- Each parameter is a compact `QLabel + QLineEdit` pair
- QLineEdit uses QValidator for format checking
- Red border + tooltip on invalid input
- "▶ 自动拟合" button is accent-colored, right-aligned
- ParamToolBar has its own visibility toggle in the Activity Bar

### 5.2 matplotlib Chart Area

Dual-pane chart rendered by matplotlib with QtAgg backend:

```
┌───────────────────────┬───────────────────────┐
│                       │                       │
│     e-j 曲线图        │    Tafel 拟合图        │
│                       │                       │
│   (左轴: E / 电流)    │    (右轴: η vs log|j|) │
│                       │                       │
│                       │                       │
└───────────────────────┴───────────────────────┘
```

- `FigureCanvasQTAgg` embedded in a QWidget via `QVBoxLayout`
- matplotlib `GridSpec(1,2)` for dual plots
- Draggable legends retained from current implementation
- Data point hover tooltips (coordinates display)

### 5.3 ChartToolBar

```
[↺ 重置] [🔍+] [🔍-] [✋平移] [▭框选]  |  [💾保存图片] [📋复制]
```

- Custom QToolBar replacing default matplotlib `NavigationToolbar2QT`
- Each tool is a `QPushButton` with consistent styling
- **框选 tool** activates manual mode: crosshair cursor, drag to select region, auto-fit on release
- Active tool highlighted with accent color

### Manual mode interaction flow

1. Click "▭框选" → cursor changes to CrossCursor
2. Drag on Tafel plot → semi-transparent rectangle highlights selection
3. Release → auto-fit on selected x-range
4. Selection remains visible (lightly shaded region)
5. Click "↺ 重置" or re-run auto-fit → exit manual mode

### 5.4 StatusBar

- Single `QLabel` at very bottom of central area
- Shows file name, segment count, last operation result
- No scrolling text — single-line only

---

## 6. Comparison Mode

### Mode switching

- Tab control at top of chart area: "单文件分析" / "跨文件对比"
- Switching tabs hides/Shows the `ComparisonPanel` in the side panels
- Side panel automatically switches to ComparisonPanel when entering compare mode
- ParamToolBar is disabled (grayed out) in compare mode — parameters don't apply

### Cross-file rendering

- All comparison items rendered on shared axes
- Each item gets its own color (from assigned palette color)
- Both e-j curve and Tafel fit line rendered per item
- Items can be individually toggled on/off via checkbox without removing

### Legend format

```
sample_1.tdms-第1段 (89.3 mV/dec)
我的对照样-第3段 (124.7 mV/dec)
sample_3.txt-第1段 (86.1 mV/dec)
```

- Only file alias, segment number, and slope in parentheses
- No R² in legend
- If an item is hidden (unchecked), its legend entry is also hidden

### Comparison summary table

Below comparison panel, a `QTableWidget` showing:

| 别名 | 段 | 斜率 (mV/dec) | R² | 点数 |
|------|-----|---------------|-----|------|
| sample_1 | 1 | 89.3 | 0.994 | 18 |
| 我的对照样 | 3 | 124.7 | 0.987 | 22 |

- Sortable by clicking column headers
- Copy-paste support (Ctrl+C from table)
- Updated when items are added/removed/re-fitted

---

## 7. Color Management

Color management is a cross-cutting feature used in both single-file and comparison modes. The PySide6 migration preserves all existing color data structures while improving the interaction UI.

### Data model (unchanged from current)

```python
# Palette schemes: named collections of segment colors
palette_schemes: dict[str, dict[int, str]]
# e.g. {"默认方案": {0: "#b90746", 1: "#0891b2", ...}, "方案一": {...}}

# Slot count per scheme (defines how many color slots exist)
palette_scheme_slot_counts: dict[str, int]

# Active scheme name
active_palette_scheme: str

# Current file's segment colors (overrides palette)
segment_colors: dict[int, str]
```

All color serialization (`deserialize_segment_colors`, `serialize_segment_colors`, `normalize_color_value`) remains in `gui/palette.py` unchanged.

### Segment color assignment (single-file mode)

In the SegmentPanel, each row has a **color strip** (8px-wide QFrame on the left side):

```
┌──────────────────────────────────┐
│ ██  ◉  第1段  R²=0.997          │ ← color strip: #b90746
│──────────────────────────────────│
│ ██  ○  第2段  R²=0.992          │ ← color strip: #0891b2
└──────────────────────────────────┘
```

- Clicking the color strip opens `QColorDialog`
- New color is set on the segment immediately
- Segment color can also be changed via the **palette scheme apply** feature

### Palette scheme management dialog

A `QDialog` (replacing the current `CTkToplevel`):

```
┌──────────────────────────────────────────────┐
│  配色方案管理                     [✕] 关闭    │
├──────────────┬───────────────────────────────┤
│  方案列表     │  颜色设置: 当前方案 "默认方案"    │
│              │                               │
│  ◉ 默认方案  │  ██ 第1段  [#b90746  ] [应用]  │
│  ○ 方案一    │  ██ 第2段  [#0891b2  ] [应用]  │
│  ○ 方案二    │  ██ 第3段  [#eab308  ] [应用]  │
│              │  ...                          │
│              │                               │
│  [📁 新增]   │  [+ 新增颜色位]               │
│  [🗑 删除]   │                               │
├──────────────┴───────────────────────────────┤
│  [应用方案到当前分段]  [应用方案到对比]          │
└──────────────────────────────────────────────┘
```

**Key interactions**:

| Element | Behavior |
|---------|----------|
| 方案列表 | QListWidget, click to select. Selected item highlighted with accent background |
| 颜色预览块 | QFrame with colored background, click opens QColorDialog |
| Hex 输入 | QLineEdit with regex validator `^#[0-9a-fA-F]{6}$` |
| [应用] | Validates hex, saves to scheme, updates preview |
| [+ 新增颜色位] | Appends one slot; new slot gets default color from `COMPARISON_COLORS` |
| [📁 新增] | Read name from input, create empty scheme with 8 default slots |
| [🗑 删除] | Confirm dialog → delete scheme (block deleting last scheme) |
| [应用方案到当前分段] | Map scheme colors to current file's segments by index |
| [应用方案到对比] | Map scheme colors to comparison items by position (cyclically) |

### Color synchronization

When a color changes (via any path: segment panel, palette manager, comparison item):

1. Update `segment_colors` or palette scheme data model
2. `refresh_segment_buttons()` → rebuild segment panel rows
3. `refresh_comparison_list()` → rebuild comparison panel rows
4. If in single mode: `draw()` with updated colors
5. If in compare mode: `render_comparison()` with updated colors
6. Auto-save settings (debounced 1s)

### Comparison item color

Each comparison item's color dot (⬤) in the comparison panel:

- Click → `QColorDialog`
- Updates `item.color` and the corresponding `segment_colors[file_path][segment_index]`
- Immediate re-render on the chart

---

## 8. Theme & Visual Style

### Color palette

```yaml
accent: "#2563eb"        # Primary blue — buttons, links, active state
accent_hover: "#1d4ed8"  # Darker blue
success: "#16a34a"       # Green — processed, OK
warning: "#f59e0b"       # Amber — manual mode
danger: "#dc2626"        # Red — delete, error
purple: "#7c3aed"        # Purple — export, palette mgmt

bg_window: "#f8fafc"     # Main window background
bg_card: "#ffffff"       # Panel/card background
bg_hover: "#f1f5f9"      # Row hover
border: "#e2e8f0"        # Dividers, borders

text_primary: "#0f172a"  # Main text
text_secondary: "#64748b" # Secondary text
text_disabled: "#94a3b8" # Disabled state
```

### Typography

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| Panel title | 13px | 600 | Section headers |
| Body | 12px | 400 | Labels, inputs |
| Secondary | 11px | 400 | Channel info, hints |
| Status | 10px | 400 | Status bar |
| Mono | 12px | 400 | Result table |

Font stack: `Segoe UI, Microsoft YaHei, sans-serif`

### Spacing

4px grid: padding 16px, component gap 8px, section gap 24px.

### QSS approach

- Component-level QSS stylesheets applied per-widget
- No global QSS on QApplication (avoids conflicts with matplotlib)
- Consistent `border-radius: 6px` for buttons, `4px` for inputs
- Inputs: 1px solid border, `#e2e8f0` default, `#2563eb` on focus
- Buttons: solid fill with hover state, no gradient
- Cards/panels: white background, no border, separated by background color contrast

### Icons

- Transition period: Unicode characters and Qt built-in icons
- Target: SVG icon set (Lucide or Material Icons) for all toolbar/activity bar icons

---

## 9. Migration Plan

### Phase 1 — Minimal Viable Qt (estimated 5-7 days)

1. Set up PySide6 dependency, migrate `gui/app.py` to `QMainWindow` shell
2. Implement main layout: activity bar + side panels + central area (matplotlib canvas)
3. Port one panel (FilePanel) end-to-end to validate architecture
4. Verify core computation imports and QThread integration

### Phase 2 — Panel Porting (estimated 5-7 days)

5. FormulaPanel — formula entry, channel list, inline validation
6. SegmentPanel — segment list with custom delegates, active/selected state
7. ParamToolBar — parameter inputs with validators, run button
8. ChartToolBar — custom toolbar, manual mode, zoom/pan reset

### Phase 3 — Comparison & Polish (estimated 3-5 days)

9. ComparisonPanel — item list, checkbox toggle, color picker, rename
10. Comparison rendering — shared axes, legend formatting
11. Summary table — QTableWidget, sorting, clipboard export
12. Theme polish — QSS refinement, spacing, hover states, focus rings

### Parallel workstream

- Packaging: Verify PySide6 + matplotlib QtAgg works with PyInstaller
- Backward compatibility: `gui/app.py` facade updated to re-export from new Qt-based module

---

## 10. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PyInstaller Qt packaging issues | Medium | Test early with a minimal bundle; use `--collect-all PySide6` |
| matplotlib QtAgg backend differences | Low | Currently using TkAgg, switch to QtAgg is well-documented |
| QThread vs current threading model | Low | Replace `threading.Thread` with `QThread` + `QObject.moveToThread` |
| CJK font rendering in Qt | Low | Qt handles CJK natively; set font via QFontDatabase |
| Migration duration underestimation | Medium | Phase 1 validates architecture quickly; adjust scope after it |

---

## 11. Out of Scope

- `core/` module changes (types, fitting, readers, formula, export, CLI)
- Python version upgrade
- CI/CD pipeline changes
- Dark mode (future consideration)
- Web/Electron deployment
