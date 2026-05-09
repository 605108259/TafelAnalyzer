from __future__ import annotations

from typing import Any


def stop_worker(worker: Any | None, *, timeout_ms: int = 3000) -> None:
    """Disconnect common QThread signals and stop a running worker."""
    if worker is None:
        return
    is_running = getattr(worker, "isRunning", None)
    if callable(is_running) and not is_running():
        return
    for signal_name in ("finished", "error"):
        signal = getattr(worker, signal_name, None)
        disconnect = getattr(signal, "disconnect", None)
        if callable(disconnect):
            try:
                disconnect()
            except Exception:
                pass
    quit_worker = getattr(worker, "quit", None)
    if callable(quit_worker):
        quit_worker()
    wait_worker = getattr(worker, "wait", None)
    if callable(wait_worker):
        wait_worker(timeout_ms)
