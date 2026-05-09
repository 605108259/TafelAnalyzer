from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeSignal:
    def __init__(self) -> None:
        self.disconnect_count = 0

    def disconnect(self) -> None:
        self.disconnect_count += 1


class FakeWorker:
    def __init__(self, running: bool = True) -> None:
        self.finished = FakeSignal()
        self.error = FakeSignal()
        self._running = running
        self.quit_count = 0
        self.wait_timeout = None

    def isRunning(self) -> bool:
        return self._running

    def quit(self) -> None:
        self.quit_count += 1
        self._running = False

    def wait(self, timeout: int) -> None:
        self.wait_timeout = timeout


class WorkerUtilsTests(unittest.TestCase):
    def test_stop_worker_disconnects_signals_and_waits_when_running(self) -> None:
        from ui.controllers.worker_utils import stop_worker

        worker = FakeWorker(running=True)

        result = stop_worker(worker, timeout_ms=1234)

        self.assertIsNone(result)
        self.assertEqual(worker.finished.disconnect_count, 1)
        self.assertEqual(worker.error.disconnect_count, 1)
        self.assertEqual(worker.quit_count, 1)
        self.assertEqual(worker.wait_timeout, 1234)

    def test_stop_worker_returns_none_without_touching_missing_worker(self) -> None:
        from ui.controllers.worker_utils import stop_worker

        self.assertIsNone(stop_worker(None))


if __name__ == "__main__":
    unittest.main()
