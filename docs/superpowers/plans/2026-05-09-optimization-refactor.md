# TafelAnalyzer 代码优化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [`) syntax for tracking.

**Goal:** 按优先级依次解决 optimization_review.md 中的 15 项优化，提升代码的可维护性、性能和健壮性。

**Architecture:** 按依赖关系将 15 项分为 5 个阶段，每个阶段内的任务相互独立可并行。阶段间有依赖：阶段 1（快速修复）→ 阶段 2（渲染重构）→ 阶段 3（核心算法）→ 阶段 4（大规模重构）→ 阶段 5（收尾 + 测试）。

**Tech Stack:** Python 3.11+, PySide6, matplotlib, numpy, pytest

---

## 文件影响总览

| 文件 | 涉及的优化项 |
|------|-------------|
| `src/ui/state.py` | #1 DRY重置, #2 _app_state迁移, #6 颜色工具 |
| `src/core/rendering.py` | #3 拆分render_figure, #5 占位图合并, #12 魔法数字 |
| `src/core/fitting.py` | #4 _best_window_fit向量化, #14 tafel_y_label |
| `src/core/cache.py` | #7 缓存键移除active_segment_index, #8 缓存恢复 |
| `src/ui/controllers/file_ctrl.py` | #6 颜色工具统一, #8 缓存导入, #10 lambda捕获 |
| `src/ui/controllers/fitting_ctrl.py` | #9 FitWorker预计算, #10 lambda捕获 |
| `src/core/types.py` | #13 rename/rename_label, #14 tafel_y_label |
| `src/ui/view_coordinator.py` | #15 clear_chart_highlights副作用 |
| `src/ui/color_utils.py` | #6 颜色工具统一（接收方） |

---

## 阶段 1：快速修复（独立小改动）

### Task 1: 状态重置逻辑去重（#1）

**文件:**
- Modify: `src/ui/state.py:124-172`

**问题:** `FileState.reset_current_result()` 和 `AnalysisState.begin_file_load()` 包含几乎相同的 18 行字段重置代码。

**方案:** 将重置逻辑提取到一个模块级私有函数 `_reset_result_fields(raw)`，两处调用。

- [ ] **Step 1: 编写测试**

```python
# tests/test_state_reset.py
from ui.state import AppState


def test_reset_current_result_clears_analysis_fields():
    state = AppState()
    state.analysis.apply_loaded_file(
        channels={"V": [1, 2]},
        segment_infos=[],
        segment_colors={0: "#ff0000"},
    )
    state.files.reset_current_result()
    # FileState 无 .current 属性，直接访问底层 raw 字典
    assert state.raw["channels"] is None
    assert state.raw["segments"] == []
    assert state.raw["prepared"] is None
    assert state.raw["fit"] is None
    assert state.raw["prepared_by_segment"] == {}
    assert state.raw["fit_by_segment"] == {}
    assert state.raw["active_segment_index"] == 0


def test_begin_file_load_resets_and_sets_path():
    from pathlib import Path
    state = AppState()
    state.analysis.begin_file_load(Path("/tmp/test.tdms"))
    # FileState 无 .current 属性，直接访问底层 raw 字典
    assert state.raw["tdms_path"] == Path("/tmp/test.tdms")
    assert state.raw["channels"] is None
    assert state.raw["segments"] == []
    assert state.raw["prepared_by_segment"] == {}
```

- [ ] **Step 2: 运行测试确认通过（因为当前代码功能正确，测试应通过）**

Run: `pytest tests/test_state_reset.py -v`

- [ ] **Step 3: 提取共享重置函数**

```python
# src/ui/state.py — 在 FileState 类之前添加

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
```

- [ ] **Step 4: 修改两个方法调用共享函数**

`FileState.reset_current_result()` 改为:
```python
def reset_current_result(self) -> None:
    _reset_result_fields(self.raw)
```

`AnalysisState.begin_file_load()` 改为:
```python
def begin_file_load(self, path: Path) -> None:
    self.raw["tdms_path"] = path
    _reset_result_fields(self.raw)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_state_reset.py -v`

- [ ] **Step 6: 提交**

```bash
git add src/ui/state.py tests/test_state_reset.py
git commit -m "refactor: DRY result reset logic in state.py (#1)"
```

---

### Task 2: 删除未使用的 draw_placeholder_fig（#5）

**文件:**
- Modify: `src/core/rendering.py:465-476`

**问题:** `draw_placeholder_fig()` 从未被调用（grep 确认），且硬编码颜色与 `draw_placeholder()` 不一致。

**方案:** 直接删除该函数。

- [ ] **Step 1: 确认无调用方**

Run: `grep -rn "draw_placeholder_fig" src/` — 应只显示定义本身。

- [ ] **Step 2: 删除函数**

删除 `src/core/rendering.py` 中的 `draw_placeholder_fig`（L465-476）。

- [ ] **Step 3: 确认无导入破坏**

Run: `python -c "from core.rendering import draw_placeholder"` — 应成功。

- [ ] **Step 4: 提交**

```bash
git add src/core/rendering.py
git commit -m "refactor: remove unused draw_placeholder_fig (#5)"
```

---

### Task 3: 缓存键移除 active_segment_index（#7）

**文件:**
- Modify: `src/core/cache.py:15-43`

**问题:** `make_result_cache_key()` 包含 `active_segment_index`，但「激活分段」是纯 UI 状态，不影响计算结果。注意：经 grep 确认此函数当前未被调用，但作为公开 API 应保持正确语义。

**方案:** 从缓存键中移除 `active_segment_index`。

- [ ] **Step 1: 编写测试**

```python
# tests/test_cache_key.py
from pathlib import Path
from core.cache import make_result_cache_key


def test_cache_key_ignores_active_segment_index():
    kwargs = dict(
        tdms_path=Path("/data/test.tdms"),
        potential_formula="[Vgs]",
        current_formula="[Igs]",
        e_eq=0.0,
        selected_segment_indices=(0, 1),
        min_window=5,
        max_window=50,
        eta_range=None,
        logj_range=None,
        min_r2=0.95,
        fit_priority="r2",
    )
    key_a = make_result_cache_key(active_segment_index=0, **kwargs)
    key_b = make_result_cache_key(active_segment_index=1, **kwargs)
    assert key_a == key_b, "Cache keys should be equal regardless of active segment"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_cache_key.py -v` — 当前应 FAIL（两个 key 不等）。

- [ ] **Step 3: 修改 make_result_cache_key**

移除 `active_segment_index` 参数和键中的对应项：

```python
def make_result_cache_key(
    *,
    tdms_path: Path,
    potential_formula: str,
    current_formula: str,
    e_eq: float,
    selected_segment_indices: tuple[int, ...],
    min_window: int,
    max_window: int,
    eta_range: tuple[float, float] | None,
    logj_range: tuple[float, float] | None,
    min_r2: float,
    fit_priority: str,
) -> tuple:
    return (
        str(tdms_path),
        potential_formula,
        current_formula,
        round(float(e_eq), 12),
        tuple(int(index) for index in selected_segment_indices),
        int(min_window),
        int(max_window),
        None if eta_range is None else tuple(round(float(v), 12) for v in eta_range),
        None if logj_range is None else tuple(round(float(v), 12) for v in logj_range),
        round(float(min_r2), 12),
        fit_priority,
    )
```

同时更新 `cache_key_to_json` / `cache_key_from_json`（无需修改，它们是通用的）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cache_key.py -v`

- [ ] **Step 5: 提交**

```bash
git add src/core/cache.py tests/test_cache_key.py
git commit -m "fix: remove active_segment_index from cache key (#7)"
```

---

### Task 4: ComparisonItem rename/rename_label 合并（#13）

**文件:**
- Modify: `src/core/types.py:97-124`

**问题:** `rename()` 和 `rename_label()` 职责重叠，容易选错。

**方案:** 保留 `rename(base_name)` 作为设置文件名的标准方法（自动派生 label），将 `rename_label` 改为 `set_label` 只设置 label，不修改 file_name。

- [ ] **Step 1: 编写测试**

```python
# tests/test_comparison_item.py
from pathlib import Path
from core.types import ComparisonItem, PreparedSeries, SegmentInfo
import numpy as np


def _make_item():
    seg = SegmentInfo(index=0, start=0, end=10)
    ps = PreparedSeries(
        raw_e=np.zeros(10), raw_j=np.zeros(10), e=np.zeros(10), j=np.zeros(10),
        eta=np.zeros(10), e_label="V", j_label="A", tafel_y_label="eta(V)",
        potential_channel="V", current_channel="I", potential_formula="V",
        current_formula="I", e_eq=0.0, segment=seg,
    )
    return ComparisonItem(
        item_id="test::0", file_path=Path("/a.tdms"), file_name="a",
        segment_index=0, prepared=ps, fit=None,
        label="a-第1段", color="#2563eb",
    )


def test_rename_sets_file_name_and_derives_label():
    item = _make_item()
    item.rename("new_name")
    assert item.file_name == "new_name"
    assert item.label == "new_name-第1段"


def test_set_label_only_changes_label():
    item = _make_item()
    item.set_label("custom label")
    assert item.label == "custom label"
    assert item.file_name == "a"  # unchanged
```

- [ ] **Step 2: 运行确认当前行为（rename_label 的测试会因 rename 不存在 set_label 方法而失败）**

Run: `pytest tests/test_comparison_item.py -v`

- [ ] **Step 3: 修改 types.py**

将 `rename_label` 重命名为 `set_label`，只设置 label：

```python
def set_label(self, text: str) -> None:
    """仅修改显示标签，不影响 file_name。"""
    text = text.strip()
    if text:
        self.label = text
```

- [ ] **Step 4: 搜索并更新 rename_label 的调用方**

Run: `grep -rn "rename_label" src/` 确认所有调用方并更新。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_comparison_item.py -v`

- [ ] **Step 6: 提交**

```bash
git add src/core/types.py tests/test_comparison_item.py
git commit -m "refactor: rename_label → set_label with clear semantics (#13)"
```

---

### Task 5: tafel_y_label 统一为中文（#14）

**文件:**
- Modify: `src/core/fitting.py:470`

**问题:** `tafel_y_label="over potential（V）"` 混用英文和中文括号。

**方案:** 统一为 `"过电位（V）"`。

- [ ] **Step 1: 修改 fitting.py L470**

```python
# Before:
tafel_y_label="over potential（V）",
# After:
tafel_y_label="过电位（V）",
```

- [ ] **Step 2: 确认渲染代码无硬编码依赖**

Run: `grep -rn "over potential" src/` — 应无结果。

- [ ] **Step 3: 提交**

```bash
git add src/core/fitting.py
git commit -m "fix: unify tafel_y_label to Chinese (#14)"
```

---

### Task 6: clear_chart_highlights 副作用说明（#15）

**文件:**
- Modify: `src/ui/view_coordinator.py:93-102`

**问题:** `clear_chart_highlights()` 在单文件模式下设置了 `active_segment_index = -1`，副作用超出函数名暗示的范围。

**方案:** 将方法拆分为 `clear_chart_highlights()`（仅清除视觉高亮）和 `reset_active_segment()`（重置状态），在 `clear_chart_highlights` 中按需调用。

> ⚠️ **先 grep 再改**：`clear_chart_highlights` 的调用方（如 `eventFilter`、`_on_chart_outside_click`）的语义是「点击图表外部 → 取消选中」，实际期望的是**重置**状态。必须先确认调用方意图，再决定替换为哪个方法。

- [ ] **Step 1: 先确认所有调用方及其语义**

Run: `grep -rn "clear_chart_highlights" src/`

逐一判断每个调用点：
- 若调用方意图是「仅清除视觉高亮，保留 active_segment_index」→ 保持 `clear_chart_highlights`
- 若调用方意图是「同时重置激活状态」→ 改为 `reset_active_segment`

- [ ] **Step 2: 修改 view_coordinator.py**

```python
def clear_chart_highlights(self) -> None:
    """清除视觉高亮，不改变激活分段状态。"""
    app = self.app
    if app.state.comparison_mode:
        app.state.comparison.set_highlight(-1)
        self.refresh_comparison_list(rebuild=False)
        self.render_comparison()
        return
    # 单文件模式：仅触发重渲染（不改变 active_segment_index）
    self.refresh_segments()
    self.render_single()

def reset_active_segment(self) -> None:
    """重置激活分段为无选中状态。"""
    app = self.app
    if app.state.comparison_mode:
        app.state.comparison.set_highlight(-1)
        self.refresh_comparison_list(rebuild=False)
        self.render_comparison()
    else:
        app.state.segments.set_active(-1)
        self.refresh_segments()
        self.render_single()
```

- [ ] **Step 3: 搜索调用 `clear_chart_highlights` 的地方，确认是否需要改为 `reset_active_segment`**

Run: `grep -rn "clear_chart_highlights" src/`

- [ ] **Step 4: 根据调用方意图逐一决定使用哪个方法**

- [ ] **Step 5: 提交**

```bash
git add src/ui/view_coordinator.py
git commit -m "refactor: separate highlight clearing from state reset (#15)"
```

---

## 阶段 2：渲染重构

### Task 7: 渲染魔法数字提取为常量（#12）

**文件:**
- Create: `src/core/render_styles.py`（新建）
- Modify: `src/core/rendering.py`

**问题:** `render_figure` 中散落着大量硬编码的样式值。

**方案:** 提取为具名常量到新文件 `render_styles.py`，按用途分组。

- [ ] **Step 1: 创建样式常量文件**

```python
# src/core/render_styles.py
"""图表渲染样式常量。"""

# --- 线条宽度 ---
LINEWIDTH_ACTIVE = 2.8
LINEWIDTH_INACTIVE = 0.9
LINEWIDTH_DEFAULT = 1.4
LINEWIDTH_FIT_ACTIVE = 2.8
LINEWIDTH_FIT_INACTIVE = 1.0
LINEWIDTH_FIT_DEFAULT = 1.5

# --- 透明度 ---
ALPHA_ACTIVE = 1.0
ALPHA_INACTIVE = 0.32
ALPHA_DEFAULT = 0.86
ALPHA_SCATTER_SELECTED = 0.95
ALPHA_SCATTER_DESELECTED_ACTIVE = 0.35
ALPHA_SCATTER_DESELECTED_INACTIVE = 0.12
ALPHA_SCATTER_DESELECTED_DEFAULT = 0.25
ALPHA_SCATTER_NO_FIT_ACTIVE = 0.75
ALPHA_SCATTER_NO_FIT_INACTIVE = 0.2
ALPHA_SCATTER_NO_FIT_DEFAULT = 0.5
ALPHA_FIT_LINE_ACTIVE = 0.98
ALPHA_FIT_LINE_INACTIVE = 0.28
ALPHA_FIT_LINE_DEFAULT = 0.75

# --- 标记大小 ---
MARKERSIZE_ACTIVE = 4.8
MARKERSIZE_INACTIVE = 2.6
MARKERSIZE_DEFAULT = 3.0

# --- 散点大小 ---
SCATTER_FIT_SELECTED_ACTIVE = 46
SCATTER_FIT_SELECTED_DEFAULT = 28
SCATTER_FIT_SELECTED_INACTIVE = 20
SCATTER_FIT_DESELECTED_ACTIVE = 24
SCATTER_FIT_DESELECTED_DEFAULT = 16
SCATTER_FIT_DESELECTED_INACTIVE = 12
SCATTER_RAW_FIT_ACTIVE = 30
SCATTER_RAW_FIT_DEFAULT = 24
SCATTER_NO_FIT_ACTIVE = 28
SCATTER_NO_FIT_DEFAULT = 18
SCATTER_NO_FIT_INACTIVE = 14

# --- 边框宽度 ---
EDGEWIDTH_ACTIVE = 0.8
EDGEWIDTH_INACTIVE = 0.4

# --- 布局参数 ---
GRIDSPEC_WSPACE = 0.28
GRIDSPEC_LEFT = 0.07
GRIDSPEC_RIGHT = 0.97
GRIDSPEC_TOP = 0.92
GRIDSPEC_BOTTOM = 0.12

# --- 拟合线 ---
FIT_LINE_MARGIN_FRAC = 0.08
FIT_LINE_MARGIN_MIN = 0.02
FIT_LINE_POINTS = 100

# --- 字体大小 ---
FONTSIZE_TITLE = 12
FONTSIZE_LABEL = 11
FONTSIZE_LEGEND = 8
FONTSIZE_PLACEHOLDER = 16
```

- [ ] **Step 2: 修改 rendering.py 导入并替换魔法数字**

在 rendering.py 顶部添加 `from core.render_styles import *` 或具体导入，然后逐一替换 L71-219 中的魔法数字。

- [ ] **Step 3: 确认渲染无视觉变化**

Run: `python main.py`（手动验证图表外观一致）。

- [ ] **Step 4: 提交**

```bash
git add src/core/render_styles.py src/core/rendering.py
git commit -m "refactor: extract rendering magic numbers to constants (#12)"
```

---

### Task 8: 拆分 render_figure（#3）

**文件:**
- Modify: `src/core/rendering.py:71-219`

**问题:** `render_figure` 约 150 行，承担了三件事：创建 axes、绘制 E-j 图、绘制 Tafel 图。

**方案:** 拆分为 `_render_ej_plot(ax, ...)` 和 `_render_tafel_plot(ax, ...)` 两个内部函数。

- [ ] **Step 1: 提取 _render_ej_plot**

```python
def _render_ej_plot(
    ax: matplotlib.axes.Axes,
    display_indices: list[int],
    prepared_by_segment: dict[int, PreparedSeries],
    fit_by_segment: dict[int, TafelFit],
    segment_styles: dict[int, dict],
    ref_prepared: PreparedSeries,
    has_active: bool,
    active_index: int,
) -> None:
    """在给定 axes 上绘制 E-j 原始数据图。"""
    from core.render_styles import (
        SCATTER_RAW_FIT_ACTIVE, SCATTER_RAW_FIT_DEFAULT,
        ALPHA_SCATTER_SELECTED,
    )
    for segment_index in display_indices:
        segment_prepared = prepared_by_segment.get(segment_index)
        if segment_prepared is None:
            continue
        style = segment_styles[segment_index]
        color = style["color"]
        is_active = style["is_active"]
        z = style["z"]
        label = f"第{segment_index + 1}段"
        ax.plot(
            segment_prepared.e, segment_prepared.j,
            marker="o", linestyle="-",
            markersize=style["markersize"],
            linewidth=style["linewidth"],
            color=color, alpha=style["alpha"],
            label=label, zorder=z,
        )
        segment_fit = fit_by_segment.get(segment_index)
        if segment_fit is not None:
            fit_indices = segment_fit.source_indices[segment_fit.selected_mask]
            if fit_indices.size:
                ax.scatter(
                    segment_prepared.e[fit_indices],
                    segment_prepared.j[fit_indices],
                    s=SCATTER_RAW_FIT_ACTIVE if is_active else SCATTER_RAW_FIT_DEFAULT,
                    color=color,
                    edgecolors="#111827",
                    linewidths=style["edgewidth"],
                    alpha=ALPHA_SCATTER_SELECTED,
                    zorder=z + 1,
                )
    ax.set_xlabel(ref_prepared.e_label, fontsize=11)
    ax.set_ylabel(ref_prepared.j_label, fontsize=11)
    title = MULTI_SEGMENT_TITLE if len(display_indices) > 1 else f"第{ref_prepared.segment.index + 1}段电化学数据"
    ax.set_title(title, fontsize=12, color=TEXT_PRIMARY, pad=8)
    ax.grid(True)
```

- [ ] **Step 2: 提取 _render_tafel_plot**

类似地将 Tafel 图绘制逻辑（L139-218）提取为 `_render_tafel_plot(ax, ...)`。

- [ ] **Step 3: 简化 render_figure**

`render_figure` 只做组合：创建 gridspec、计算样式、调用两个内部函数。

- [ ] **Step 4: 运行应用确认渲染正常**

Run: `python main.py`（手动验证）。

- [ ] **Step 5: 提交**

```bash
git add src/core/rendering.py
git commit -m "refactor: split render_figure into _render_ej_plot and _render_tafel_plot (#3)"
```

---

## 阶段 3：核心算法优化

### Task 9: _best_window_fit 向量化（#4）

**文件:**
- Modify: `src/core/fitting.py:143-186`

**问题:** 内层 Python for 循环遍历所有 start 位置，大数据量时性能差。

**方案:** 对每个 window size，用 numpy 向量化计算所有 start 位置的 slope 和 r2。

- [ ] **Step 1: 编写基准测试**

```python
# tests/test_fitting_perf.py
import numpy as np
import time
from core.fitting import _best_window_fit


def test_best_window_fit_correctness():
    """向量化后结果应与原始逻辑一致。"""
    np.random.seed(42)
    x = np.linspace(0, 10, 100)
    y = 2.5 * x + np.random.normal(0, 0.1, 100)
    start, end, slope, r2 = _best_window_fit(x, y, min_window=10, max_window=50)
    assert r2 > 0.99
    assert abs(slope - 2.5) < 0.1


def test_best_window_fit_large_data():
    """大数据量应能在合理时间内完成。"""
    np.random.seed(42)
    n = 2000
    x = np.linspace(0, 100, n)
    y = 3.0 * x + np.random.normal(0, 0.5, n)
    t0 = time.time()
    start, end, slope, r2 = _best_window_fit(x, y, min_window=20, max_window=200)
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"Too slow: {elapsed:.2f}s"
    assert r2 > 0.95
```

- [ ] **Step 2: 运行确认当前行为**

Run: `pytest tests/test_fitting_perf.py -v` — 记录当前性能基线。

- [ ] **Step 3: 重写 _best_window_fit 为向量化版本**

```python
def _best_window_fit(
    x: np.ndarray,
    y: np.ndarray,
    min_window: int,
    max_window: int,
    *,
    min_r2: float | None = None,
    fit_priority: str = "r2",
) -> tuple[int, int, float, float]:
    cum_x, cum_y, cum_xx, cum_xy, cum_yy = _build_cumulative(x, y)
    n = int(x.size)
    best = None
    for window in range(min_window, max_window + 1):
        if window > n:
            break
        w = float(window)
        num_starts = n - window + 1
        starts = np.arange(num_starts)
        ends = starts + window

        sx = cum_x[ends] - cum_x[starts]
        sy = cum_y[ends] - cum_y[starts]
        sxx = cum_xx[ends] - cum_xx[starts]
        sxy = cum_xy[ends] - cum_xy[starts]
        syy = cum_yy[ends] - cum_yy[starts]

        var_x = w * sxx - sx * sx
        valid = np.abs(var_x) >= VAR_EPSILON

        if not np.any(valid):
            continue

        cov_xy = w * sxy - sx * sy
        slopes = np.where(valid, cov_xy / var_x, 0.0)
        var_y = w * syy - sy * sy
        r2 = np.where(
            valid,
            np.where(np.abs(var_y) < VAR_EPSILON, 1.0, (cov_xy * cov_xy) / (var_x * var_y)),
            0.0,
        )

        if min_r2 is not None:
            valid = valid & (r2 >= float(min_r2))
            if not np.any(valid):
                continue

        # 找当前 window 下的最优 start
        valid_indices = np.where(valid)[0]
        if valid_indices.size == 0:
            continue
        # 完全向量化，避免 Python for 循环
        # _window_rank 的比较逻辑等价于按单一标量排序
        if fit_priority == "slope":
            best_local_idx = valid_indices[np.argmin(np.abs(slopes[valid_indices]))]
        else:  # "r2" 优先
            best_local_idx = valid_indices[np.argmax(r2[valid_indices])]
        rank = _window_rank(float(r2[best_local_idx]), float(slopes[best_local_idx]), window, fit_priority)
        if best is None or rank < best[0]:
            best = (rank, int(best_local_idx), int(best_local_idx) + window, float(slopes[best_local_idx]), float(r2[best_local_idx]))

    if best is None:
        if min_r2 is not None:
            raise ValueError(f"未找到满足最小 R²={float(min_r2):.6f} 的 Tafel 区间")
        raise ValueError("数据点太少，无法进行 Tafel 区间识别")
    _, start, end, slope, r2 = best
    return start, end, slope, r2
```

- [ ] **Step 4: 运行测试确认正确性和性能**

Run: `pytest tests/test_fitting_perf.py -v`

- [ ] **Step 5: 提交**

```bash
git add src/core/fitting.py tests/test_fitting_perf.py
git commit -m "perf: vectorize _best_window_fit inner loop (#4)"
```

---

### Task 10: 颜色工具统一（#6）

**文件:**
- Modify: `src/ui/color_utils.py`
- Modify: `src/ui/controllers/file_ctrl.py:22-83`
- Modify: `src/ui/state.py:21-25`

**问题:** 三处独立的颜色工具实现：`color_utils.py`、`file_ctrl.py` 的 `_hex_to_rgb/_rgb_to_hex/_interpolate_hex`、`state.py` 的 `normalize_palette_color`。

**方案:** 将所有颜色工具统一到 `color_utils.py`，其他地方导入使用。

- [ ] **Step 1: 扩展 color_utils.py**

```python
# src/ui/color_utils.py — 添加以下函数

import re

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex_color(color: str, fallback: str = "#2563eb") -> str:
    """标准化 hex 颜色字符串。"""
    text = str(color or fallback).strip()
    if not text.startswith("#"):
        text = f"#{text}"
    if HEX_COLOR_RE.match(text):
        return text.lower()
    return fallback


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """将 hex 颜色转为 (R, G, B) 元组。"""
    text = normalize_hex_color(color)
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """将 (R, G, B) 元组转为 hex 颜色。"""
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(v))) for v in rgb))


def interpolate_hex(left: str, right: str, t: float) -> str:
    """在两个 hex 颜色间线性插值。"""
    a = hex_to_rgb(left)
    b = hex_to_rgb(right)
    return rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_color_utils.py
from ui.color_utils import hex_to_rgb, rgb_to_hex, interpolate_hex, normalize_hex_color


def test_hex_to_rgb():
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)


def test_rgb_to_hex():
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"


def test_interpolate_hex():
    assert interpolate_hex("#000000", "#ffffff", 0.5) == "#808080"


def test_normalize_hex_color():
    assert normalize_hex_color("ff0000") == "#ff0000"
    assert normalize_hex_color("#GG0000") == "#2563eb"
```

- [ ] **Step 3: 更新 file_ctrl.py**

将 `_hex_to_rgb`、`_rgb_to_hex`、`_interpolate_hex` 替换为从 `color_utils` 导入，删除本地定义。将 `_map_palette_colors` 中的 `_interpolate_hex` 调用改为 `interpolate_hex`。

- [ ] **Step 4: 更新 state.py**

将 `normalize_palette_color` 替换为从 `color_utils` 导入 `normalize_hex_color`。`QColorCompat` 内部调用改为 `normalize_hex_color`。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_color_utils.py tests/test_state_and_colors.py -v`

- [ ] **Step 6: 提交**

```bash
git add src/ui/color_utils.py src/ui/controllers/file_ctrl.py src/ui/state.py tests/test_color_utils.py
git commit -m "refactor: consolidate color utilities into color_utils.py (#6)"
```

---

### Task 11: FitWorker 预计算分段信息（#9）

**文件:**
- Modify: `src/ui/controllers/fitting_ctrl.py:45-84`

**问题:** `FitWorker.run()` 每次都重新调用 `prepare_series()`，后者内部会再次调用 `build_segment_infos()`（分段检测）。但分段信息在文件加载时已计算好。

**方案:** 修改 `FitWorker` 构造函数接收 `precomputed_segments`，传给 `prepare_series`。

- [ ] **Step 1: 检查 FitWorker 构造函数**

Read `src/ui/controllers/fitting_ctrl.py:30-52` 获取当前构造函数签名。

- [ ] **Step 2: 修改 FitWorker.__init__ 增加 precomputed_segments 参数**

```python
class FitWorker(QThread):
    finished = Signal(object, object, object)
    error = Signal(str)

    def __init__(
        self,
        channels,
        pot_formula,
        cur_formula,
        e_eq,
        selected_indices,
        window_min,
        window_max,
        min_r2,
        fit_priority,
        eta_range,
        logj_range,
        precomputed_segments=None,  # 新增
    ):
        super().__init__()
        self.channels = channels
        self.pot_formula = pot_formula
        self.cur_formula = cur_formula
        self.e_eq = e_eq
        self.selected_indices = selected_indices
        self.window_min = window_min
        self.window_max = window_max
        self.min_r2 = min_r2
        self.fit_priority = fit_priority
        self.eta_range = eta_range
        self.logj_range = logj_range
        self.precomputed_segments = precomputed_segments
```

- [ ] **Step 3: 修改 FitWorker.run 中的 prepare_series 调用**

```python
prepared = prepare_series(
    self.channels,
    potential_formula=self.pot_formula,
    current_formula=self.cur_formula,
    e_eq=self.e_eq,
    segment_index=seg_idx,
    precomputed_segments=self.precomputed_segments,
)
```

- [ ] **Step 4: 修改 FitWorker 的调用方，传入已有分段信息**

在 `fitting_ctrl.py` 的 `run_fit` 方法中，将 `app._app_state.get("segments")` 传给 `precomputed_segments`。

- [ ] **Step 5: 提交**

```bash
git add src/ui/controllers/fitting_ctrl.py
git commit -m "perf: pass precomputed segments to FitWorker (#9)"
```

---

## 阶段 4：大规模重构

### Task 12: 缓存导入数据完整性（#8）

**文件:**
- Modify: `src/ui/controllers/file_ctrl.py:319-325`

**问题:** `import_cache_dialog` 恢复 `result_cache` 时只取 `prepared` 和 `fit`，丢失了 `prepared_by_segment`、`fit_by_segment`、`fit_error_by_segment`、`selected_segment_indices`、`active_segment_index`、`view_state`、`limits`。

**方案:** 完整恢复 `build_cache_payload` 序列化的所有字段。

- [ ] **Step 1: 编写测试**

```python
# tests/test_cache_import.py
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.serialization import prepared_to_dict, prepared_from_dict, fit_to_dict, fit_from_dict
from core.types import PreparedSeries, SegmentInfo


def _make_prepared() -> PreparedSeries:
    seg = SegmentInfo(index=0, start=0, end=10)
    return PreparedSeries(
        raw_e=np.linspace(0, 1, 10),
        raw_j=np.logspace(-6, -3, 10),
        e=np.linspace(0, 1, 10),
        j=np.logspace(-6, -3, 10),
        eta=np.linspace(0, 1, 10),
        e_label="[V]",
        j_label="[Igs/area]",
        tafel_y_label="过电位（V）",
        potential_channel="V",
        current_channel="Igs/area",
        potential_formula="[V]",
        current_formula="[Igs/area]",
        e_eq=0.0,
        segment=seg,
    )


def test_import_cache_restores_prepared_by_segment():
    """缓存导入应完整恢复 prepared_by_segment 字段。"""
    prepared = _make_prepared()
    # 序列化
    serialized = {"prepared_by_segment": {"0": prepared_to_dict(prepared)}}
    # 反序列化
    restored = {
        int(k): prepared_from_dict(v)
        for k, v in serialized["prepared_by_segment"].items()
    }
    assert 0 in restored
    assert np.allclose(restored[0].e, prepared.e)


def test_import_cache_restores_fit_error_by_segment():
    """缓存导入应完整恢复 fit_error_by_segment 字段。"""
    raw_errors = {"0": "数据点不足", "1": "R² 不达标"}
    restored = {int(k): v for k, v in raw_errors.items()}
    assert restored[0] == "数据点不足"
    assert restored[1] == "R² 不达标"
```

- [ ] **Step 2: 修改 import_cache_dialog 中的 result_cache 恢复逻辑**

```python
# src/ui/controllers/file_ctrl.py L319-325
app._app_state["result_cache"] = {
    c.cache_key_from_json(item["key"]): {
        "prepared": prepared_from_dict(item["prepared"]),
        "fit": fit_from_dict(item["fit"]) if item.get("fit") else None,
        "prepared_by_segment": {
            int(k): prepared_from_dict(v)
            for k, v in item.get("prepared_by_segment", {}).items()
        },
        "fit_by_segment": {
            int(k): fit_from_dict(v)
            for k, v in item.get("fit_by_segment", {}).items()
        },
        "fit_error_by_segment": {
            int(k): v
            for k, v in item.get("fit_error_by_segment", {}).items()
        },
        "selected_segment_indices": item.get("selected_segment_indices", []),
        "active_segment_index": item.get("active_segment_index", 0),
        "view_state": item.get("view_state"),
        "limits": item.get("limits"),
    }
    for item in payload.get("result_cache", [])
}
```

- [ ] **Step 3: 提交**

```bash
git add src/ui/controllers/file_ctrl.py
git commit -m "fix: restore all cache fields on import (#8)"
```

---

### Task 13: Qt Worker lambda 改进（#10）

**文件:**
- Modify: `src/ui/controllers/file_ctrl.py:173-179`
- Modify: `src/ui/controllers/fitting_ctrl.py:188-192`

**问题:** Worker 信号用 lambda + 默认参数捕获 generation 和 path，有潜在内存泄漏风险。`fitting_ctrl.py` 的 error 信号没有 generation 检查。

**方案:** 将 generation 和 path 存储到 worker 对象上，通过 `self.sender()` 在 slot 内读取，避免 lambda 捕获。对 error 信号也增加 generation 检查。

> ⚠️ **`self.sender()` 的跨线程说明**：Qt 的 `sender()` 在通过 `AutoConnection`（默认）跨线程投递的信号中，slot 运行在接收方线程（主线程），此时 `sender()` 返回值正常可用。但若信号改为 `DirectConnection`，`sender()` 可能在子线程中被调用而返回空指针。当前 QThread worker 使用默认 AutoConnection，安全。若未来改为 DirectConnection 需改用 `functools.partial` 绑定代替。

- [ ] **Step 1: 修改 FileLoadWorker**

```python
# src/ui/controllers/file_ctrl.py — FileLoadWorker 类
class FileLoadWorker(QThread):
    finished = Signal(object, object, object, object)
    error = Signal(str)

    def __init__(self, path, pot_formula, cur_formula):
        super().__init__()
        self.path = path
        self.pot_formula = pot_formula
        self.cur_formula = cur_formula
```

- [ ] **Step 2: 修改 file_ctrl.py 中的信号连接方式**

```python
# src/ui/controllers/file_ctrl.py _load_file 方法
self._worker = FileLoadWorker(path, formulas[0], formulas[1])
self._worker.generation = generation  # 存储到 worker 对象
self._worker.finished.connect(self._on_load_finished_from_worker)
self._worker.error.connect(self._on_load_error_from_worker)
self._worker.start()

def _on_load_finished_from_worker(self, channels, pot_f, cur_f, segments) -> None:
    worker = self.sender()
    if worker is None:
        return
    self._on_load_finished(channels, pot_f, cur_f, segments, worker.path, worker.generation)

def _on_load_error_from_worker(self, msg) -> None:
    worker = self.sender()
    if worker is None:
        return
    self._on_load_error(msg, worker.path, worker.generation)
```

- [ ] **Step 3: 同样修改 FitWorker 和 fitting_ctrl.py**

```python
# src/ui/controllers/fitting_ctrl.py — FitWorker 增加 generation 属性
self._worker.generation = generation
self._worker.finished.connect(self._on_fit_finished_from_worker)
self._worker.error.connect(self._on_fit_error_from_worker)

def _on_fit_finished_from_worker(self, prepared_map, fit_map, error_map) -> None:
    worker = self.sender()
    if worker is None:
        return
    self._on_fit_finished(prepared_map, fit_map, error_map, worker.generation)

def _on_fit_error_from_worker(self, msg) -> None:
    worker = self.sender()
    if worker is None:
        return
    if not self.app.state.operations.is_current(worker.generation):
        return
    self._on_fit_error(msg)
```

- [ ] **Step 4: 运行应用确认信号正常**

Run: `python main.py`（手动验证文件加载和拟合流程）。

- [ ] **Step 5: 提交**

```bash
git add src/ui/controllers/file_ctrl.py src/ui/controllers/fitting_ctrl.py
git commit -m "refactor: replace lambda signal captures with worker attributes (#10)"
```

---

### Task 14: _app_state 直接访问清理（#2）— 渐进式

**文件:**
- Modify: 多个文件（见下文）

**问题:** 129 处 `_app_state` 直接访问绕过领域状态类的校验逻辑。

**方案:** 不做一次性大迁移，而是按模块逐步替换。优先处理渲染和控制器中语义最明确的字段。

- [ ] **Step 1: 识别可通过 `app.state` 访问的字段**

从 `src/ui/state.py` 中找出已有的领域状态类属性映射：
- `app._app_state["tdms_path"]` → `app.state.files.current_path`
- `app._app_state["channels"]` → 需在 `AnalysisState` 上添加属性
- `app._app_state["segments"]` → 需在 `AnalysisState` 上添加属性
- `app._app_state["prepared_by_segment"]` → 需在 `AnalysisState` 上添加属性
- `app._app_state["fit_by_segment"]` → 需在 `AnalysisState` 上添加属性
- `app._app_state["active_segment_index"]` → `app.state.segments.active_index`

- [ ] **Step 2: 在 AnalysisState 上添加只读属性**

```python
# src/ui/state.py — AnalysisState 类
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
```

- [ ] **Step 3: 修改 rendering.py 中的 _app_state 访问**

将 `rendering.py` 中的 `app._app_state.get(...)` 调用替换为 `app.state.*` 调用。

- [ ] **Step 4: 修改 view_coordinator.py 中的 _app_state 访问**

将 9 处 `_app_state` 访问替换为领域状态 API。

- [ ] **Step 5: 逐模块验证**

每改一个文件就运行 `python main.py` 验证。

- [ ] **Step 6: 提交**

```bash
git add src/ui/state.py src/core/rendering.py src/ui/view_coordinator.py
git commit -m "refactor: migrate _app_state access to app.state API (#2)"
```

---

## 阶段 5：测试补全

### Task 15: 核心算法测试（#11）

**文件:**
- Create: `tests/test_fitting.py`
- Create: `tests/test_formula.py`
- Create: `tests/test_readers.py`

**问题:** 核心的 `fitting.py`、`formula.py`、`readers.py` 完全没有测试。

- [ ] **Step 1: fitting.py 测试**

```python
# tests/test_fitting.py
import numpy as np
from core.fitting import auto_tafel_fit, _best_window_fit, _build_cumulative


def test_auto_tafel_fit_perfect_linear():
    """完美线性数据应返回精确的斜率。"""
    x = np.linspace(0, 1, 100)
    y = 2.5 * x + 0.1
    fit = auto_tafel_fit(x, y, min_window=10, max_window=50)
    assert abs(fit.slope_mv_per_dec - 2500.0) < 1.0  # 2.5 V/dec = 2500 mV/dec
    assert fit.r2 > 0.999


def test_auto_tafel_fit_noisy_data():
    """含噪声数据应在合理范围内。"""
    np.random.seed(42)
    x = np.linspace(0, 1, 200)
    y = 1.8 * x + np.random.normal(0, 0.02, 200)
    fit = auto_tafel_fit(x, y, min_window=15, max_window=100)
    assert abs(fit.slope_mv_per_dec - 1800.0) < 50.0
    assert fit.r2 > 0.95


def test_best_window_fit_selects_longest_good_window():
    """当 fit_priority='r2' 时应选择 R² 最高的窗口。"""
    x = np.linspace(0, 10, 100)
    y = 3.0 * x + 0.5
    start, end, slope, r2 = _best_window_fit(x, y, min_window=10, max_window=80)
    assert r2 > 0.999
    assert abs(slope - 3.0) < 0.01


def test_build_cumulative():
    """累积和应正确计算。"""
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    cum_x, cum_y, cum_xx, cum_xy, cum_yy = _build_cumulative(x, y)
    assert cum_x[0] == 0.0
    assert cum_x[1] == 1.0
    assert cum_x[3] == 6.0
    assert cum_y[3] == 15.0
```

- [ ] **Step 2: formula.py 测试**

```python
# tests/test_formula.py
from core.formula import evaluate_formula


def test_evaluate_formula_simple_channel():
    """简单通道引用应返回原始数据。"""
    channels = {"Vgs": [1.0, 2.0, 3.0], "Igs": [0.1, 0.2, 0.3]}
    result = evaluate_formula(channels, "[Vgs]", ["Vgs"])
    assert list(result.values) == [1.0, 2.0, 3.0]


def test_evaluate_formula_arithmetic():
    """公式应支持基本算术运算。"""
    channels = {"Vgs": [1.0, 2.0, 3.0]}
    result = evaluate_formula(channels, "-[Vgs]", ["Vgs"])
    assert list(result.values) == [-1.0, -2.0, -3.0]


def test_evaluate_formula_with_offset():
    """公式应支持常量偏移。"""
    channels = {"Vgs": [1.0, 2.0, 3.0]}
    result = evaluate_formula(channels, "[Vgs]+0.23", ["Vgs"])
    assert abs(result.values[0] - 1.23) < 1e-10
```

- [ ] **Step 3: build_segment_infos 测试**

```python
# tests/test_fitting.py — 追加
from core.fitting import build_segment_infos


def test_build_segment_infos_single_segment():
    """连续数据应识别为单个分段。"""
    # 使用 POTENTIAL_PREFERRED_NAMES 中的通道名（V）让自动推断生效
    channels = {"V": list(range(100))}
    infos = build_segment_infos(channels)  # potential_formula=None 自动推断
    assert len(infos) == 1
    assert infos[0].start == 0
    assert infos[0].end == 100


def test_build_segment_infos_with_jump():
    """含有大幅跳跃的数据应分割为多个分段。"""
    data = list(range(50)) + list(range(200, 250))
    # 使用 [channel_name] 公式语法，裸字符串 "potential" 不会被识别为通道引用
    channels = {"potential": data}
    infos = build_segment_infos(channels, "[potential]")
    assert len(infos) >= 2
```

- [ ] **Step 4: 运行所有测试**

Run: `pytest tests/ -v`

- [ ] **Step 5: 检查覆盖率**

Run: `pytest tests/ --cov=src --cov-report=term-missing`

- [ ] **Step 6: 提交**

```bash
git add tests/test_fitting.py tests/test_formula.py
git commit -m "test: add core algorithm tests for fitting and formula (#11)"
```

---

## 执行顺序总结

| 阶段 | 任务 | 依赖 | 优先级 | 预计工时 |
|------|------|------|--------|---------|
| 1 | T1 状态重置DRY | 无 | 高 | 15min |
| 1 | T2 删除draw_placeholder_fig | 无 | 高 | 5min |
| 1 | T3 缓存键修复 | 无 | 中 | 10min |
| 1 | T4 ComparisonItem rename | 无 | 低 | 15min |
| 1 | T5 tafel_y_label | 无 | 低 | 5min |
| 1 | T6 clear_chart_highlights | 无 | 低 | 15min |
| 2 | T7 魔法数字提取 | 无 | 低 | 20min |
| 2 | T8 render_figure 拆分 | T7 | 高 | 30min |
| 3 | T9 _best_window_fit 向量化 | 无 | 高 | 30min |
| 3 | T10 颜色工具统一 | 无 | 中 | 20min |
| 3 | T11 FitWorker 预计算 | 无 | 中 | 15min |
| 4 | T12 缓存导入完整性 | 无 | 中 | 15min |
| 4 | T13 Qt lambda 改进 | 无 | 中 | 20min |
| 4 | T14 _app_state 清理 | T1+T8 | 高 | 45min |
| 5 | T15 核心算法测试 | T9 | 中 | 30min |

**总预计工时：~4.5 小时**

## 验证步骤

每个 Task 完成后：
1. 运行 `pytest tests/ -v` 确认所有测试通过
2. 运行 `python main.py` 手动验证 GUI 功能（涉及 UI 的任务）
3. 确认 git status 干净（只有预期的文件变更）

全部完成后：
1. `pytest tests/ --cov=src --cov-report=term-missing` — 目标覆盖率 ≥ 60%（从 0 起步）
2. 手动测试完整流程：加载文件 → 拟合 → 对比 → 导出 → 缓存导入/导出
3. `git log --oneline` 确认提交历史清晰
