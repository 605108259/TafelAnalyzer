"""公式解析与求值引擎。

支持 `[ChannelName]` 占位符和 + - * / ** 运算符。
"""
from __future__ import annotations

import ast
from functools import lru_cache
from typing import Iterable

import numpy as np

from core.types import CHANNEL_REF_PATTERN, FormulaResult
from core.utils import pick_channel_name, resolve_channel_name


def normalize_formula(
    channels: dict[str, np.ndarray],
    formula: str | None,
    preferred: Iterable[str],
) -> str:
    text = (formula or "").strip()
    if not text:
        text = f"[{pick_channel_name(channels, preferred)}]"
    references: list[str] = []

    def _replace(match) -> str:
        resolved = resolve_channel_name(channels, match.group(1).strip())
        references.append(resolved)
        return f"[{resolved}]"

    normalized = CHANNEL_REF_PATTERN.sub(_replace, text)
    if not references:
        raise ValueError("公式中至少需要一个 channel，占位格式如 [Vgs]+0.23")
    return normalized


def _ast_eval(node: ast.AST, env: dict[str, np.ndarray]) -> np.ndarray | float:
    if isinstance(node, ast.Expression):
        return _ast_eval(node.body, env)
    if isinstance(node, ast.BinOp):
        left = _ast_eval(node.left, env)
        right = _ast_eval(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise ValueError("公式仅支持 + - * / **")
    if isinstance(node, ast.UnaryOp):
        operand = _ast_eval(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("公式仅支持一元 + 和 -")
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError(f"未知变量：{node.id}")
        return env[node.id]
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("公式中只能使用数字常量")
    raise ValueError("公式包含不支持的语法")


@lru_cache(maxsize=128)
def _parse_expression(expression: str) -> ast.Expression:
    return ast.parse(expression, mode="eval")


def evaluate_formula(
    channels: dict[str, np.ndarray],
    formula: str | None,
    preferred: Iterable[str],
    *,
    start: int = 0,
    end: int | None = None,
) -> FormulaResult:
    normalized = normalize_formula(channels, formula, preferred)
    env: dict[str, np.ndarray] = {}
    min_length: int | None = None
    resolved_refs = []
    for match in CHANNEL_REF_PATTERN.finditer(normalized):
        resolved = match.group(1)
        if resolved not in resolved_refs:
            resolved_refs.append(resolved)
    if not resolved_refs:
        raise ValueError("公式中至少需要一个 channel，占位格式如 [Vgs]+0.23")
    token_map: dict[str, str] = {}
    for index, ref in enumerate(resolved_refs):
        arr = np.asarray(channels[ref], dtype=float)
        values = arr.ravel()[start:end]
        if min_length is None:
            min_length = int(values.size)
        else:
            min_length = min(min_length, int(values.size))
        token_map[ref] = f"ch_{index}"
        env[token_map[ref]] = values
    if min_length is None or min_length <= 0:
        raise ValueError("公式对应的有效数据为空")
    for token in list(env):
        env[token] = env[token][:min_length]
    expression = CHANNEL_REF_PATTERN.sub(lambda m: token_map[m.group(1)], normalized)
    try:
        parsed = _parse_expression(expression)
    except SyntaxError as exc:
        raise ValueError(f"公式语法错误：{normalized}") from exc
    values = _ast_eval(parsed, env)
    values_array = np.asarray(values, dtype=float).ravel()
    if values_array.size == 1:
        values_array = np.full(min_length, float(values_array[0]), dtype=float)
    elif values_array.size != min_length:
        raise ValueError("公式结果长度与 channel 长度不一致")
    return FormulaResult(
        values=values_array,
        formula=normalized,
        primary_channel=resolved_refs[0],
        references=tuple(resolved_refs),
    )
