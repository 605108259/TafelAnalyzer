# CLAUDE.md

本文档为 Claude Code 在此仓库中工作时提供指导。

## 项目概述

Tafel Analyzer (TAFSQ) — 电化学 Tafel 斜率分析桌面应用。支持 TDMS、CorrWare (.cor)、txt/csv/xlsx 数据文件的自动分段、Tafel 线性拟合、可视化及跨文件对比。

技术栈：Python 3、CustomTkinter（GUI）、matplotlib（图表）、numpy（计算）、nptdms（TDMS 读取）、pandas（表格读取）、tkinterdnd2（拖拽）。

## 目录结构

```
数据处理/
├── main.py                       # GUI 启动入口（将 src 加入 sys.path）
├── run_cli.py                    # CLI 启动入口
├── requirements.txt              # Python 依赖
├── CLAUDE.md                     # 项目文档（本文件）
├── tdms_tafel_gui.spec           # PyInstaller 打包配置
├── TafelAnalyzer_Setup.iss       # Inno Setup 安装脚本
├── tdms_tafel_gui_settings.json  # 用户设置模板（配色方案/参数默认值）
├── data/                         # 示例/测试数据
├── icons/                        # 图标资源（ico/png）
├── build/                        # PyInstaller 构建缓存
├── dist/                         # 打包输出
├── installer_output/             # 安装包输出
└── src/
    ├── __init__.py
    ├── tdms_tafel.py             # [facade] 向后兼容，全部重导出自 core/
    ├── tdms_tafel_gui.py         # [facade] 向后兼容，全部重导出自 gui/
    ├── core/                     # 纯逻辑层（无 GUI 依赖）
    │   ├── __init__.py           # 统一导出 core 所有公有 API
    │   ├── types.py              # 数据类 TafelFit/SegmentInfo/PreparedSeries/FormulaResult
    │   ├── utils.py              # CJK 字体解析、channel 名称解析
    │   ├── readers.py            # 文件读取：TDMS / COR / 表格
    │   ├── formula.py            # 公式解析引擎：AST eval + [Channel] 占位符
    │   ├── fitting.py            # Tafel 拟合 + 自动分段检测
    │   ├── export.py             # 导出 txt / npz / 图片
    │   └── cli.py                # CLI 参数解析 + 处理入口
    └── gui/                      # CustomTkinter 图形界面
        ├── __init__.py           # 导出 TafelAnalyzerApp
        ├── app.py                # 主应用类 TafelAnalyzerApp（324 行）
        ├── app_builder.py        # UI 控件创建工厂（350 行）
        ├── settings.py           # 设置持久化（加载/保存 JSON）
        ├── palette.py            # 调色板方案管理（颜色定义、CRUD、管理器对话框）
        ├── rendering.py          # matplotlib 图表渲染、图例/视图状态管理
        ├── comparison.py         # 对比模式图表渲染与导出
        ├── cache.py              # 结果缓存构建与序列化
        ├── widgets.py            # UI 组件工厂（entry/combo/option 等）
        ├── serialization.py      # TafelFit/PreparedSeries/SegmentInfo ↔ dict
        ├── theme.py              # UI 主题颜色常量 + matplotlib rcParams
        └── controllers/
            ├── __init__.py       # 导出所有控制器
            ├── file_mgr.py       # FileManager — 文件加载/切换/缓存
            ├── fitting_ctrl.py   # FittingController — 拟合编排/手动模式
            ├── export_mgr.py     # ExportManager — 单段/批量/对比导出
            ├── comparison_mgr.py # ComparisonManager — 对比项管理/渲染
            └── segment_panel.py  # SegmentPanel — 分段按钮/勾选/切换
```

## 核心架构

### 分层设计

```
main.py / run_cli.py
    |
    +---> gui.app.TafelAnalyzerApp  (CustomTkinter GUI)
    |         |
    |         +---> gui/settings.py     (持久化)
    |         +---> gui/palette.py      (颜色管理)
    |         +---> gui/rendering.py    (matplotlib 渲染)
    |         +---> gui/comparison.py   (对比模式)
    |         +---> gui/cache.py        (结果缓存)
    |         +---> gui/widgets.py      (UI 工厂)
    |         +---> gui/serialization.py (数据 ↔ dict)
    |         +---> gui/theme.py        (样式常量)
    |
    +---> core/ (纯逻辑，无 GUI 依赖)
              |
              +---> types.py      TafelFit, SegmentInfo, PreparedSeries, FormulaResult
              +---> utils.py      CJK 字体解析, channel 名称解析
              +---> readers.py    read_data_all_channels() 统一入口
              +---> formula.py    evaluate_formula() AST 表达式求值器
              +---> fitting.py    auto_tafel_fit() + build_segment_infos()
              +---> export.py     export_processed_txt() + export_fit_npz() + plot_tafel()
              +---> cli.py        argparse CLI
```

### 数据流

```
文件 (tdms/cor/txt/csv/xlsx)
    |
    v
read_data_all_channels()         [readers.py]
    |  返回 dict[str, ndarray]
    v
evaluate_formula() + normalize_formula()  [formula.py]
    |  解析 [ChannelName] 占位符, AST 求值
    v
build_segment_infos()            [fitting.py]
    |  检测跳变/电压反向边界
    v
prepare_series()                 [fitting.py]
    |  返回 PreparedSeries (eta, e, j 切片至该段)
    v
auto_tafel_fit() / manual_tafel_fit()  [fitting.py]
    |  滑动窗口 + prefix-sum O(1) 回归 + 区域扩展
    v
TafelFit (dataclass: slope, intercept, R2, mask)
    |
    +---> export_processed_txt() / export_fit_npz() / plot_tafel()  [export.py]
    +---> gui 渲染 (matplotlib FigureCanvasTkAgg)
    +---> 缓存至 result_cache dict
```

### 关键数据类型（`core/types.py`）

| 类型 | 用途 | 关键字段 |
|------|------|----------|
| `TafelFit` | 拟合结果（不可变） | slope_v_per_dec, intercept_v, r2, selected_mask, source_indices, mode |
| `SegmentInfo` | 分段边界 | index, start, end |
| `PreparedSeries` | 处理后的分段数据 | raw_e, raw_j, e, j, eta, e_label, j_label, e_eq, segment |
| `FormulaResult` | 公式求值结果 | values, formula, primary_channel, references |
| `ComparisonItem` | 跨文件对比条目 | item_id, file_path, file_name, segment_index, prepared, fit, label, color |

## 模块 Codemap

### core/ — 纯逻辑层

#### `core/types.py`（117 行）
- **导出**: TafelFit, SegmentInfo, PreparedSeries, FormulaResult, ComparisonItem, COMPARISON_COLORS, channel 名称常量, `_normalize_optional_range()`
- **依赖**: numpy, re, dataclasses
- **说明**: 除 ComparisonItem 外所有 dataclass 均为 frozen（不可变）

#### `core/utils.py`（63 行）
- **导出**: `_channel_basename()`, `resolve_channel_name()`, `pick_channel_name()`, `get_cjk_font_name()`, `apply_matplotlib_cjk()`
- **依赖**: matplotlib.font_manager, numpy
- **说明**: `get_cjk_font_name()` 使用 LRU 缓存，尝试 Microsoft YaHei > SimHei > ... > DejaVu Sans

#### `core/readers.py`（104 行）
- **导出**: `read_data_all_channels()`, `read_tdms_all_channels()`, `read_corrw_cor_channels()`, `read_table_channels()`
- **依赖**: nptdms, pandas, openpyxl/xlrd, numpy
- **说明**: `read_data_all_channels()` 按后缀名分派。COR 文件使用基于正则的列解析（tab/逗号/空格分隔符）。表格读取按 utf-8-sig > utf-8 > gb18030 > latin-1 顺序回退。

#### `core/formula.py`（129 行）
- **导出**: `normalize_formula()`, `evaluate_formula()`
- **依赖**: ast（stdlib）, numpy
- **被依赖**: fitting.py, cli.py
- **说明**: 使用 Python `ast.parse()` 进行安全表达式求值。支持 + - * / ** 运算符。`[ChannelName]` 占位符被解析并替换为 token 变量。`_parse_expression` 使用 LRU 缓存（maxsize=128）。

#### `core/fitting.py`（470 行）
- **导出**: `auto_tafel_fit()`, `manual_tafel_fit()`, `build_segment_infos()`, `prepare_series()`，内部辅助 `_r2_score`, `_linear_fit`, `_prepare_xy`, `_fit_from_selected`, `_window_rank`, `_best_window_fit`, `_expand_region`
- **依赖**: core.types, core.formula, numpy
- **算法**: `_best_window_fit` 使用前缀和数组（cum_x, cum_y, cum_xx, cum_xy, cum_yy）实现 O(1) 每窗口回归。`_expand_region` 贪心地向最佳窗口两侧扩展。`build_segment_infos` 检测电位信号中的跳变（大差值）和方向反转。
- **说明**: min_window=6, max_window=30（可配置）。拟合优先级："r2" 或 "slope"。

#### `core/export.py`（145 行）
- **导出**: `export_txt()`, `export_processed_txt()`, `export_fit_npz()`, `plot_tafel()`
- **依赖**: numpy, matplotlib, core.types, core.utils

#### `core/cli.py`（84 行）
- **导出**: `main()`
- **依赖**: argparse, core.readers, core.fitting, core.export
- **使用**: `python run_cli.py <file> --potential-formula ... --segment 1`

### gui/ — GUI 层

#### `gui/app.py`（324 行）
- **类**: `TafelAnalyzerApp(DndCTk)` — 主应用（薄编排层）
- **关键方法**:
  - `__init__`: `_init_app_state() → build_*() → _init_controllers() → _wire_callbacks() → _finish_startup()`
  - `_wire_callbacks()`: 将 30+ 控件事件绑定到控制器方法
  - `_save_current_file_ui_state()`: 读取 widget 值保存（UI 紧耦合，保留在 app.py）
  - `_format_result()`: 格式化结果文本（保留在 app.py）
  - `_switch_mode()`: 单文件/对比模式面板切换 + 视图状态保存
  - `_handle_app_close()`: 保存设置后销毁窗口
- **控制器**: `self.files`, `self.fitting`, `self.export_mgr`, `self.comparison`, `self.segments`

#### `gui/settings.py`（148 行）
- **导出**: `load_app_settings()`, `save_app_settings()`, `persist_parameter_settings()`, `normalize_parameter_settings()`, `collect/apply_parameter_settings_from_form()`, `current_file_key()`, `find_label_by_path()`, `get_segment_selection_text()`
- **持久化路径**: `%APPDATA%/Tafel Analyzer/tdms_tafel_gui_settings.json`

#### `gui/palette.py`（707 行）
- **导出**: 颜色 CRUD（`normalize_color_value`, `get/set/remove_palette_scheme_color`, `set_segment_color_for_path`, `get_segment_color`），方案管理（`normalize_palette_scheme_name`, `refresh_palette_scheme_options`, `open_palette_scheme_manager`），应用函数（`apply_palette_scheme_to_current`, `apply_palette_scheme_to_comparison`）
- **UI**: `open_palette_scheme_manager()` 创建 CTkToplevel 对话框，左侧为方案列表，右侧为颜色网格

#### `gui/rendering.py`（418 行）
- **导出**: `render_figure()`（多段）, `draw()`（单模式入口）, `draw_placeholder()`, `refresh_selector()`（手动模式的 RectangleSelector）, `capture/apply_plot_view_state()`, `capture/apply_legend_state()`
- **说明**: 使用 `matplotlib.rc_context(MPL_RC)` 保证样式一致性。图例可拖拽。视图状态以 dict 形式捕获（xlim/ylim/图例位置），在重新渲染时恢复。

#### `gui/comparison.py`（186 行）
- **导出**: `render_comparison()`, `render_comparison_empty()`, `build_comparison_export()`, `comparison_item_id()`
- **说明**: 对比模式在相同坐标轴上用不同颜色渲染多个条目的 e-j 和 Tafel 图。

#### `gui/cache.py`（122 行）
- **导出**: `make_result_cache_key()`, `build_cache_payload()`, `export_cache_file()`, `cache_key_to/from_json()`
- **说明**: 缓存键是所有输入参数的元组，用作 `result_cache` 字典的键。完整项目状态可序列化为 JSON 并恢复。

#### `gui/widgets.py`（198 行）
- **导出**: `make_section_label()`, `make_entry_row()`, `make_combo_row()`, `set_combo_values()`, `set_option_values()`, `set_entry_text()`, `path_labels()`, `output_stem()`, `parse_range_text()`, `resolved_output_stem()`, `priority_label_to_key()`, `priority_key_to_label()`, `parse_segment_selection()`, `segment_selection_text()`
- **说明**: `RANGE_TEXT_PATTERN` 正则验证 "min-max" 范围格式。`parse_segment_selection` 支持逗号分隔和 "all" 关键字。

#### `gui/serialization.py`（78 行）
- **导出**: `segment_to/from_dict()`, `prepared_to/from_dict()`, `fit_to/from_dict()`
- **说明**: 将 numpy 数组转换为列表或反向转换。用于缓存和剪贴板操作。

#### `gui/theme.py`（41 行）
- **导出**: 颜色常量（ACCENT, BG_LIGHT, CARD_BG, TEXT_PRIMARY 等），`MPL_RC` 字典（matplotlib 样式覆盖），`PLOT_FONT`。

### Facade 模块

#### `src/tdms_tafel.py`（58 行）
向后兼容 facade — 所有导出均从 `core/` 包重新导出。新代码应直接从 `core` 导入。

#### `src/tdms_tafel_gui.py`（61 行）
向后兼容 facade — 所有导出均从 `gui/` 包重新导出。包含 `build_app()` 工厂函数。新代码应直接从 `gui` 导入。

## 设计模式

### 1. 跨模块函数调用模式（无委托）

GUI 模块使用 `app` 参数模式 + `TYPE_CHECKING` 避免循环导入。调用方直接调用模块函数，而非通过 app 委托：

```python
# gui/palette.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gui.app import TafelAnalyzerApp

def some_function(app: TafelAnalyzerApp, ...):
    ...  # 接收 app 参数的函数

def pure_function(name: str) -> str:
    ...  # 不接收 app 参数的纯函数
```

app.py 或其他模块调用时直接使用模块函数：

```python
# gui/settings.py 或 gui/app.py
from gui import palette as p

p.some_function(app, ...)   # 正确：函数接受 app
p.pure_function(name)       # 正确：纯函数不传 app
```

**关键规则**：调用 `module.function(app, ...)` 前必须确认函数签名确实接收 `app` 作为第一个参数。不接收 `app` 的纯函数不可传入 `app`。

**验证**：每次重构后运行 `python src/scripts/verify_refactor.py`，自动检查所有跨模块调用参数一致性。

### 2. 应用状态容器
所有应用状态存储在 `self._app_state: dict` 中，避免与 `tkinter.CTk.state()` 冲突：
```python
self._app_state: dict = {
    "selected_paths": [],
    "tdms_path": None,
    "channels": None,
    "segments": [],
    "segment_colors": {},
    "palette_schemes": {},
    ...
}
```

### 3. 后台线程与 Generation Counter
拟合在守护线程中执行。generation 计数器（`_op_generation`）防止过期结果生效：
```python
self._app_state["_op_generation"] += 1
current_gen = self._app_state["_op_generation"]
# ... 在后台线程中 ...
cancelled=lambda: self._app_state["_op_generation"] != current_gen
```

### 4. 结果缓存与版本控制
缓存键是所有输入参数的元组。相同输入产生相同键时直接复用缓存结果，无需重新计算。`_restore_or_autorun()` 优先检查缓存，若未命中则回退到 `_run_fit()`。

### 5. 每个文件的 UI 状态持久化
`file_ui_cache` 存储每个路径的 UI 状态（公式、参数、分段选择、颜色）。在 `_load_current_file()` 时恢复。全局设置（调色板方案、参数默认值）存储在 `%APPDATA%/Tafel Analyzer/tdms_tafel_gui_settings.json`。

## 关键约定

- 公式字符串使用 `[ChannelName]` 引用通道
- 所有拟合逻辑在后台守护线程中执行；UI 通过 `app.after(0, callback)` 更新
- 调色板方案：`{scheme_name: {segment_index: hex_color}}`
- 分段索引：内部 0-based，用户显示 1-based
- 电压/电流首选通道名称定义在 `POTENTIAL_PREFERRED_NAMES` / `CURRENT_PREFERRED_NAMES` 中
- 窗口范围格式："min-max"（例如 "12-15"），由 `parse_range_text()` 解析
- 分段选择格式：逗号分隔的 1-based 索引 + "all" 关键字

## 构建与部署

```bash
# 安装依赖
pip install -r requirements.txt

# 运行 GUI
python main.py

# 运行 CLI
python run_cli.py data/file.tdms --fit-priority slope --min-r2 0.95

# 打包为可执行文件
pyinstaller tdms_tafel_gui.spec

# 构建安装程序（需要 Inno Setup）
# 先运行 pyinstaller，然后使用 Inno Setup 编译 TafelAnalyzer_Setup.iss
```

### PyInstaller 说明
- `tdms_tafel_gui.spec` 包含所有 `core/` 和 `gui/` 子模块的 hidden imports
- 图标等数据文件通过 `datas` 收集
- spec 文件根据配置使用 `--onefile` 或 `--onedir`

### Inno Setup 说明
- `TafelAnalyzer_Setup.iss` 定义了 AppId、版本、发行商
- 使用 `dist\TafelAnalyzer` 作为源目录
- 输出：`installer_output\TAFSQ_setup.exe`

## 迁移记录（单体 → 模块化）

- `src/tdms_tafel.py`（单体逻辑）→ `src/core/` 包
- `src/tdms_tafel_gui.py`（单体 GUI）→ `src/gui/` 包
- 旧单体文件保留为向后兼容的 facade（仅重新导出）
- `self.state` 重命名为 `self._app_state`，避免覆盖 `tkinter.CTk.state()`
- 提取的模块函数通过 `app` 参数获取应用引用
- < 200 行模块：readers, formula, export, utils, serialization, cache, comparison, theme, settings
- 200-500 行模块：widgets, rendering, fitting, cli, palette
- 2350 行：app.py（主 GUI 类 — 因事件连线保持单文件内聚）

## 设置文件

用户设置保存在 `%APPDATA%/Tafel Analyzer/tdms_tafel_gui_settings.json`：

```json
{
  "palette_schemes": {
    "默认方案": {"0": "#b90746", "1": "#0891b2", ...},
    "方案一": {"0": "#b90746", "1": "#d70428", ...}
  },
  "palette_scheme_slot_counts": {"默认方案": 10, "方案一": 12},
  "active_palette_scheme": "方案一",
  "saved_parameter_defaults": {
    "e_eq": "0", "window_range": "12-15",
    "eta_range": "", "logj_range": "",
    "min_r2": "0.95", "fit_priority": "斜率更低优先"
  }
}
```
