from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from ui.app import TafelAnalyzerApp


class BaseAppController(QObject):
    """Base class for controllers. Holds app reference for state access."""

    def __init__(self, app: TafelAnalyzerApp):
        super().__init__(app)
        self.app = app
