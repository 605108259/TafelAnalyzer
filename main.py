"""Tafel Analyzer GUI 启动入口 (PySide6 Qt 版本)"""
import sys
from pathlib import Path

# 将 src 目录加入模块搜索路径
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from PySide6.QtWidgets import QApplication
from gui_qt.app import TafelAnalyzerApp

qapp = QApplication(sys.argv)
window = TafelAnalyzerApp()
window.show()
sys.exit(qapp.exec())
