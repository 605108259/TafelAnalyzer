"""文件读取：TDMS / COR / 表格（CSV/TXT/XLSX）。"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def read_tdms_all_channels(tdms_path: Path) -> dict[str, np.ndarray]:
    from nptdms import TdmsFile

    tdms_file = TdmsFile.read(tdms_path)
    groups = tdms_file.groups()
    out: dict[str, np.ndarray] = {}
    multiple_groups = len(groups) > 1
    for group in groups:
        for channel in group.channels():
            key = f"{group.name}/{channel.name}" if multiple_groups else channel.name
            out[key] = np.asarray(channel[:])
    return out


def _decode_text_best_effort(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_corrw_cor_channels(path: Path) -> dict[str, np.ndarray]:
    from core.types import COR_DEFAULT_HEADERS

    text = _decode_text_best_effort(path.read_bytes())
    lines = text.splitlines()
    end_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "End Comments":
            end_idx = idx
            break
    if end_idx is None or end_idx == 0:
        raise ValueError("未识别到 .cor 数据区：缺少 End Comments")
    header_line = lines[end_idx - 1].strip()
    headers = [item.strip() for item in re.split(r"[\t,]+|\s{2,}", header_line) if item.strip()]
    if not headers:
        headers = list(COR_DEFAULT_HEADERS)
    cols: list[list[float]] = [[] for _ in headers]
    for raw in lines[end_idx + 1 :]:
        line = raw.strip()
        if not line:
            continue
        parts = re.split(r"[\t, ]+", line)
        if len(parts) < len(headers):
            continue
        try:
            values = [float(parts[i]) for i in range(len(headers))]
        except ValueError:
            continue
        for col, value in zip(cols, values, strict=False):
            col.append(value)
    if not cols or not cols[0]:
        raise ValueError("未从 .cor 文件解析出有效数据行")
    return {name: np.asarray(values, dtype=float) for name, values in zip(headers, cols, strict=False)}


def read_table_channels(path: Path) -> dict[str, np.ndarray]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("读取 txt/csv/Excel 需要安装 pandas（以及 Excel 需 openpyxl/xlrd）") from exc

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(path, sep=r"[\t, ]+", engine="python", encoding="utf-8-sig")
    if df is None or df.empty:
        raise ValueError(f"文件为空或无法解析：{path.name}")
    channels: dict[str, np.ndarray] = {}
    for name in df.columns:
        key = str(name).strip()
        if not key or key.lower().startswith("unnamed"):
            continue
        values = np.asarray(pd.to_numeric(df[name], errors="coerce"), dtype=float).reshape(-1)
        channels[key] = values
    if not channels:
        raise ValueError(f"未在文件中识别到有效列：{path.name}")
    return channels


def read_data_all_channels(path: Path) -> dict[str, np.ndarray]:
    suffix = path.suffix.lower()
    if suffix == ".tdms":
        return read_tdms_all_channels(path)
    if suffix == ".cor":
        return read_corrw_cor_channels(path)
    if suffix in {".txt", ".csv", ".xlsx", ".xls"}:
        return read_table_channels(path)
    raise ValueError(f"不支持的文件格式：{suffix}")
