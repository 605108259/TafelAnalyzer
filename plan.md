## 当前主要问题

### 1. 每次保存都完整重写

位置：

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\ui\controllers\file_ctrl.py

autosave_project_history() 每次都会：

1. _cache_current_analysis_state()
2. build_cache_payload(app)
3. 把整个 payload 写回同一个 JSON

即使只是改了一个对比项名字，也会重写全部：

- 所有文件列表
- 所有 file_ui_cache
- 所有 result_cache
- 所有 PreparedSeries 数组
- 所有 TafelFit 数组
- 所有对比项数据

这是卡顿根源。

------

### 2. 无脏检查

现在只有 schedule_project_autosave()，没有判断：

- 文件列表是否真的变了
- 参数是否真的变了
- 当前结果是否已经写过
- 对比项是否只是选中状态变化
- payload 内容是否和上次一致

所以“重复点击/切换/刷新 UI”也可能触发写盘。

------

### 3. 主线程同步 I/O

当前同步写入点：

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\ui\controllers\file_ctrl.py

python



```
cache_path.write_text(...) 
```

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\ui\settings.py

python



```
APP_SETTINGS_PATH.write_text(...) 
```

这些都在 UI 主线程执行。项目稍大时必卡。

------

## 当前缓存重复项

### 重复 1：prepared 和 prepared_by_segment

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\core\cache.py

当前每个 result entry 里同时保存：

python



```
"prepared": prepared_to_dict(cached["prepared"]) "prepared_by_segment": {...} 
```

prepared 基本就是 prepared_by_segment[active_segment] 的重复。

建议：移除顶层 prepared，只保存：

json



```
"active_segment_index": 0, "prepared_by_segment": {...} 
```

------

### 重复 2：fit 和 fit_by_segment

同理：

python



```
"fit": fit_to_dict(cached["fit"]) "fit_by_segment": {...} 
```

fit 通常就是当前激活分段的 fit。

建议：移除顶层 fit，用 active_segment_index 从 fit_by_segment 恢复。

------

### 重复 3：comparison_items 里重复保存 prepared/fit

当前 comparison_items 每项保存完整：

python



```
"prepared": prepared_to_dict(item.prepared) "fit": fit_to_dict(item.fit) 
```

但这些通常已经存在于 result_cache。

建议：对比项只保存引用：

json



```
{  "item_id": "...",  "file_path": "...",  "segment_index": 1,  "result_key": "...",  "prepared_ref": "...",  "fit_ref": "...",  "label": "...",  "color": "...",  "visible": true } 
```

必要时可保存一个 fallback，但不应默认全量复制。

------

### 重复 4：limits 和 view_state

当前同时保存：

python



```
"view_state": ... "limits": ... 
```

limits 是旧格式兼容字段，现在可以只在迁移旧缓存时使用，不必继续写。

建议：v3 缓存中移除 limits。

------

### 重复 5：manual_fit_regions 同时在 file_ui_cache 和 result_cache

当前两边都有：

- file_ui_cache[path]["manual_fit_regions"]
- result_cache[key]["manual_fit_regions"]

建议：手动拟合区域属于拟合结果状态，应放在 result cache；file_ui_cache 只存 UI 参数、颜色、选中分段。

------

## 当前遗漏项

### 遗漏 1：项目元信息不在项目缓存内

现在项目标题、id、时间主要依赖 settings 的 project_history。

建议项目缓存本身加入：

json



```
"project": {  "id": "...",  "title": "...",  "created_at": "...",  "updated_at": "...",  "app_version": "...",  "cache_format_version": 3 } 
```

这样单独拖入一个缓存文件也能完整识别。

------

### 遗漏 2：对比面板高亮行

当前没有保存：

python



```
comparison_highlight_row 
```

如果用户恢复项目，希望对比面板状态一致，应保存。

------

### 遗漏 3：当前活动面板 / 当前视图

已有：

json



```
"chart_view_state": {  "active_mode": ... } 
```

但没有保存当前左侧面板，例如文件、对比、颜色、历史。

建议可选保存：

json



```
"ui_state": {  "active_panel": "files/comparison/palette/history",  "active_chart_mode": "single/comparison" } 
```

这属于项目体验项，不是核心数据项。

------

### 遗漏 4：默认视图状态

当前保存：

- single_plot_view_state
- compare_plot_view_state

但没有保存：

- single_plot_default_view_state
- compare_plot_default_view_state

如果恢复后点击 Home，可能和保存前不完全一致。

建议保存默认视图，或恢复后重新计算并明确行为。

------

## 完整修改任务

### 任务 1：建立缓存 v3 schema

新增项目缓存结构：

添加到对话

history_cache/  <project_id>/    manifest.json    file_ui.json    result_index.json    comparison.json    prepared/      <prepared_key>.json 或 .npz    fits/      <fit_key>.json

目标：

- 小改动只写小文件
- 大数组不反复重复写
- 对比项只引用已有 prepared/fit

------

### 任务 2：拆分当前 build_cache_payload()

当前：

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\core\cache.py

需要拆成：

python



```
build_project_manifest(app) build_file_ui_payload(app) build_result_index_payload(app) build_comparison_payload(app) build_prepared_blob(prepared) build_fit_blob(fit) 
```

不要再一个函数返回整包大 JSON。

------

### 任务 3：新增脏检查 DirtyTracker

新增状态：

python



```
app._app_state["project_dirty"] = {  "manifest": False,  "file_ui": set(),  "results": set(),  "comparison": False,  "view_state": False, } 
```

新增接口：

python



```
mark_project_dirty(section, key=None) schedule_project_autosave() 
```

规则：

- 改参数 → file_ui
- 拟合完成 → results
- 手动拟合 → results
- 改颜色 → file_ui 或 comparison
- 对比重命名/显隐/排序 → comparison
- 缩放/平移 → view_state
- 增删文件 → manifest

------

### 任务 4：加入 payload hash，避免无意义写入

每个分块保存前计算稳定 hash：

python



```
sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"))) 
```

如果 hash 没变，不写文件。

需要维护：

json



```
"hashes": {  "manifest": "...",  "file_ui": "...",  "comparison": "...",  "result:<key>": "..." } 
```

------

### 任务 5：改成后台异步写盘

新增：

添加到对话

D:\OneDrive\Desktop\MSIC\Q\数据处理\.worktrees\pyside6-migration\src\ui\controllers\project_save_worker.py

或放进 file_ctrl.py 先实现。

保存流程：

1. 主线程只生成轻量 snapshot。
2. worker 线程序列化和写盘。
3. 写完后 signal 回主线程更新状态。
4. 新 save 请求如果 worker 正忙，只记录 pending dirty，不并发写。

------

### 任务 6：原子写入

所有缓存写入改成：

python



```
tmp = path.with_suffix(path.suffix + ".tmp") tmp.write_text(...) tmp.replace(path) 
```

防止程序中断造成历史缓存损坏。

------

### 任务 7：迁移旧 v2 缓存

保留当前导入逻辑，但新增迁移层：

python



```
load_project_cache(path):    if cache_format_version == 2:        return migrate_v2_to_v3(payload)    if cache_format_version == 3:        return load_v3_project(path) 
```

这样用户已有历史记录不丢。

------

### 任务 8：去重 result_cache

当前每个 result cache entry 保存完整多分段数据。

改成：

json



```
"result_index": {  "<result_key>": {    "selected_segment_indices": [0, 1, 2],    "active_segment_index": 0,    "prepared_refs": {      "0": "<prepared_key>",      "1": "<prepared_key>"    },    "fit_refs": {      "0": "<fit_key>",      "1": "<fit_key>"    },    "fit_errors": {},    "manual_fit_regions": {},    "view_state": {}  } } 
```

同一个分段 prepared/fit 被多个 result 引用时，只保存一次。

------

### 任务 9：对比项引用 result/prepared/fit

当前对比项直接嵌入数组。

改成：

json



```
{  "item_id": "...",  "file_path": "...",  "file_name": "...",  "segment_index": 0,  "prepared_ref": "...",  "fit_ref": "...",  "label": "...",  "color": "...",  "visible": true } 
```

恢复时从 blob 载入。

------

### 任务 10：settings 写入也加脏检查

save_app_settings(app) 目前每次完整写 settings。

应增加：

- settings payload hash
- 没变不写
- 写入也用原子 replace

settings 小，但它现在和项目保存耦合，容易造成额外 I/O。

------

## 优先实施顺序

我建议按这个顺序做：

1. **先做脏检查 + 异步写盘 + 原子写入**
    立刻解决卡顿和无意义写入。
2. **再做 v3 分块缓存 schema**
    解决完整重写和重复大对象。
3. **再做 prepared/fit blob 去重**
    解决历史项目越来越大的问题。
4. **最后做 v2 → v3 迁移和兼容测试**
    确保旧历史记录能恢复。