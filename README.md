# TAFSQ / Tafel Analyzer

TAFSQ 是一个用于电化学 Tafel 曲线分析的 Windows 桌面软件。软件基于 PySide6 构建，支持读取 TDMS、CSV、Excel/XLSX、COR 等数据文件，自动识别分段，执行 Tafel 拟合，并提供多文件对比、配色方案管理、历史项目恢复、缓存复用和自动更新能力。

## 主要功能

- 数据导入：支持 TDMS、CSV、Excel/XLSX、COR。
- 公式计算：支持使用 `[通道名]` 引用通道并进行表达式计算；TDMS 通道不符合默认命名时会先加载文件并列出可用通道，允许手动指定电压和电流公式。
- 自动分段：自动识别曲线分段并生成可选分段列表。
- 自动拟合：按窗口范围、`R²`、`log(j)` 范围、过电位范围等参数进行 Tafel 拟合。
- 手动拟合：支持手动框选拟合区域，并缓存手动拟合区域。
- 参数默认值：文件管理面板可保存当前拟合参数，新加载文件默认沿用保存后的参数。
- 多文件对比：支持把不同文件/分段加入对比面板并独立管理显示、颜色和名称；列表重命名、上移、下移和显示切换使用增量刷新，避免大列表操作时整面板重建。
- 配色方案：支持自定义配色、渐变、反转、多选操作、取色和保存方案。
- 历史项目：项目状态自动保存，可从历史项目面板恢复。
- 缓存复用：结果缓存使用“文件指纹 + 参数”作为 key，文件移动目录后仍可复用缓存。
- 自动更新：启动时检查远端版本，发现新版本后可一键下载、校验、安装并重启。

## 运行源码

```powershell
python main.py
```

运行 CLI：

```powershell
python run_cli.py <file> [options]
```

示例：

```powershell
python run_cli.py data/*.tdms --potential-formula "-[Vgs]+0.23" --current-formula "[Igs/area]/(2.4e-7+3)" --e-eq 0
```

安装依赖：

```powershell
pip install -r requirements.txt
```

## 测试

```powershell
python -m pytest
```

基础编译检查：

```powershell
python -m compileall src tests scripts
```

## 项目结构

```text
src/
  core/                 核心业务逻辑，不依赖 GUI
    cache.py            缓存 key、历史项目缓存、v3 目录缓存
    comparison.py       对比图渲染与导出
    fitting.py          自动/手动 Tafel 拟合
    formula.py          通道公式解析与计算
    readers.py          数据读取
    rendering.py        单文件图表渲染和视图状态管理
    serialization.py    PreparedSeries / TafelFit 序列化
    version.py          应用版本号和更新地址
  ui/                   PySide6 界面层
    app.py              主窗口和面板调度
    updater.py          自动更新检查、下载、校验和安装
    controllers/        文件、拟合、对比、导出控制器
    panels/             左侧面板
    central/            右侧工作区
scripts/
  make_update_manifest.py  生成 update.json
  publish_release.py       通过 SFTP 上传发布文件
TafelAnalyzer_Setup.iss    Inno Setup 安装包脚本
```

## 版本与自动更新

当前版本号定义在：

```text
src/core/version.py
```

远端更新清单：

```text
http://107.174.62.19/tafsq/update.json
```

更新流程：

1. 软件启动后后台请求 `update.json`。
2. 比较远端 `version` 和本地 `APP_VERSION`。
3. 如果远端版本更高，弹窗提示“立即更新”。
4. 点击后下载安装包到临时目录。
5. 校验 SHA256。
6. 启动 Inno Setup 安装包静默安装。
7. 当前程序退出。
8. 安装完成后自动重新启动 TAFSQ。

详细发布流程见：

```text
docs/发布与自动更新.md
```

## 打包发布

必须用 `--paths src`，否则打包后的 exe 可能找不到 `ui` / `core` 包。

示例：

```powershell
python -m PyInstaller --noconfirm --distpath dist-1.0.6 --workpath build-1.0.6 TAFSQ.spec
```

Inno Setup Compiler 如果不在 PATH 中，可直接使用完整路径：

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" TafelAnalyzer_Setup.iss
```

## 注意事项

- 目标平台是 Windows。
- 安装目录如果位于 `Program Files`，一键更新安装阶段可能触发 Windows UAC。
- 已崩溃无法启动的旧版本不能自行自动更新，需要手动安装修复版。
- 发布新版本时必须同步更新：
  - `src/core/version.py`
  - `TafelAnalyzer_Setup.iss`
  - VPS 上的 `update.json`
