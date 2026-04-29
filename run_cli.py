"""Tafel Analyzer CLI 启动入口"""
import sys
from pathlib import Path

_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.cli import main

raise SystemExit(main())
