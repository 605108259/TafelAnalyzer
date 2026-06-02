from __future__ import annotations

from typing import Any


def stop_worker(worker: Any | None, *, timeout_ms: int = 3000) -> None:
    """Quit and wait for a running QThread worker.

    Does NOT disconnect signals — handlers use a generation check
    to ignore stale results.  Disconnecting would create a zombie
    state where the handler silently returns because sender() is None,
    leaving the UI in a permanent loading spinner.
    """
    if worker is None:
        return
    is_running = getattr(worker, "isRunning", None)
    if callable(is_running) and not is_running():
        return
    quit_worker = getattr(worker, "quit", None)
    if callable(quit_worker):
        quit_worker()
    wait_worker = getattr(worker, "wait", None)
    if callable(wait_worker):
        wait_worker(timeout_ms)
