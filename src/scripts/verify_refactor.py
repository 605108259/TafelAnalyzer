"""重构验证脚本 — 检查跨模块引用的正确性。

检查 1：跨模块函数调用参数一致性
  确保所有 `module.function(app, ...)` 调用对应的函数定义确实接受 `app` 作为第一个参数。

检查 2：残留 app._xxx 委托引用
  确保除 app.py 外的 GUI 模块不引用已删除的 TafelAnalyzerApp 委托方法。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent  # src/
GUI = SRC / "gui"
CONTROLLERS = GUI / "controllers"

# ━━ 检查 1：跨模块函数参数一致性 ━━

CHECKED_MODULES: dict[str, Path] = {
    "p": GUI / "palette.py",
    "settings": GUI / "settings.py",
    "r": GUI / "rendering.py",
    "comp": GUI / "comparison.py",
    "c": GUI / "cache.py",
    "serialization": GUI / "serialization.py",
}

CALLER_MODULES: list[Path] = [
    GUI / "settings.py",
    GUI / "palette.py",
    GUI / "app.py",
    GUI / "app_builder.py",
    CONTROLLERS / "file_mgr.py",
    CONTROLLERS / "fitting_ctrl.py",
    CONTROLLERS / "export_mgr.py",
    CONTROLLERS / "comparison_mgr.py",
    CONTROLLERS / "segment_panel.py",
]

# ━━ 检查 2：残留 app._xxx 委托引用 ━━

# TafelAnalyzerApp 上仍然有效的属性/方法（在 app.py / app_builder.py 中定义）
VALID_APP_ATTRIBUTES: set[str] = {
    # app.py — 核心方法
    "_app_state",
    "_save_current_file_ui_state",
    "_format_result",
    "_set_result",
    "_set_compare_result",
    "_switch_mode",
    "_handle_app_close",
    # app.py — 状态 keys
    "_op_generation",
    "_pending_gen",
    "_fitting_lock",
    # app_builder.py — toolbar home 原始方法
    "_toolbar_home_original",
}

# 允许使用 app._xxx 的文件（app.py 和 app_builder.py 自己定义这些属性）
ALLOWED_APP_FILES: set[str] = {"app.py", "app_builder.py"}


# ━━ 检查 1 实现 ━━

def _has_app_param(node: ast.FunctionDef) -> bool:
    if not node.args.args:
        return False
    first = node.args.args[0]
    return first.arg == "app"


def build_function_registry(mod_path: Path) -> dict[str, bool]:
    registry: dict[str, bool] = {}
    tree = ast.parse(mod_path.read_text(encoding="utf-8"), filename=str(mod_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            registry[node.name] = _has_app_param(node)
    return registry


def check_calls(
    mod_path: Path,
    module_alias: str,
    registry: dict[str, bool],
) -> list[str]:
    errors: list[str] = []
    tree = ast.parse(mod_path.read_text(encoding="utf-8"), filename=str(mod_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != module_alias:
            continue
        func_name = func.attr
        if func_name not in registry:
            continue
        takes_app = registry[func_name]
        has_app_arg = bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == "app"

        if not takes_app and has_app_arg:
            errors.append(
                f"{mod_path.name}:{node.lineno}: {module_alias}.{func_name}() "
                f"不接收 app 参数，但调用时传了 app"
            )

    return errors


# ━━ 检查 2 实现 ━━

def check_app_attribute_refs(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if path.name in ALLOWED_APP_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'app\._([a-zA-Z_]\w*)\b', text):
            attr = '_' + m.group(1)
            if attr not in VALID_APP_ATTRIBUTES:
                line_num = text[:m.start()].count('\n') + 1
                errors.append(
                    f"{path.name}:{line_num}: app.{attr} — "
                    f"TafelAnalyzerApp 上不存在此属性/方法"
                )
    return errors


# ━━ 主函数 ━━

def main() -> int:
    errors: list[str] = []

    # 检查 1：跨模块函数调用参数一致性
    registries: dict[str, dict[str, bool]] = {}
    for alias, path in CHECKED_MODULES.items():
        if not path.exists():
            errors.append(f"[错误] 模块文件不存在: {path}")
            continue
        registries[alias] = build_function_registry(path)

    for caller in CALLER_MODULES:
        if not caller.exists():
            errors.append(f"[错误] 调用者文件不存在: {caller}")
            continue
        for alias, registry in registries.items():
            errs = check_calls(caller, alias, registry)
            errors.extend(errs)

    # 检查 2：残留 app._xxx 委托引用
    all_gui_files: list[Path] = []
    for pattern in ["*.py", "controllers/*.py"]:
        all_gui_files.extend(GUI.glob(pattern))
    attr_errs = check_app_attribute_refs(all_gui_files)
    errors.extend(attr_errs)

    # 汇总
    if errors:
        print("[FAIL] 验证未通过：\n")
        for err in errors:
            print(f"  - {err}")
        print()
        return 1
    else:
        print("[OK] 所有验证通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
