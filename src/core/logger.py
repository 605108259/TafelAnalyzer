"""Application logging with rotating file handler.

Logs go to %APPDATA%/Tafel Analyzer/tafel_analyzer.log (max 1 MB, 5 backups).
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def _log_dir() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Tafel Analyzer"


LOG_PATH = _log_dir() / "tafel_analyzer.log"

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _log_dir().mkdir(parents=True, exist_ok=True)
    _logger = logging.getLogger("tafel")
    _logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=1_048_576, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    _logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    _logger.addHandler(ch)

    _logger.info(f"日志文件: {LOG_PATH}")
    return _logger


def log_info(msg: str) -> None:
    get_logger().info(msg)


def log_error(msg: str) -> None:
    get_logger().error(msg)


def log_warning(msg: str) -> None:
    get_logger().warning(msg)


def log_debug(msg: str) -> None:
    get_logger().debug(msg)


def log_exception(msg: str) -> None:
    get_logger().exception(msg)
