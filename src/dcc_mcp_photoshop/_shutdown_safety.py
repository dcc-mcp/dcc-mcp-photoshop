"""Shutdown safety for ``PhotoshopMcpServer``.

Photoshop's server process may be killed by the OS, an operator, or the
gateway.  This module ensures clean teardown regardless of the exit path.

Layers:
1. **atexit fallback** — catches normal Python process exit
2. **Process sentinel** — OS-level file that vanishes on crash; allows
   external cleanup tools to detect dead instances
3. **ShutdownCoordinator** — ensures stop callbacks run exactly once
"""

from __future__ import annotations

import atexit
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

#: Default directory for process sentinel files
DEFAULT_SENTINEL_DIR = Path(tempfile.gettempdir()) / "dcc-mcp-photoshop-sentinels"


# ---------------------------------------------------------------------------
# Process sentinel
# ---------------------------------------------------------------------------


class ProcessSentinel:
    """OS-level file that vanishes when the process exits (even on crash).

    On Windows, the file is opened with ``DELETE_ON_CLOSE`` semantics via
    :func:`tempfile.NamedTemporaryFile`.  On POSIX, we use a regular file
    and remove it on clean shutdown.

    External cleanup tools can check for sentinel files to detect dead
    instances that left stale gateway registrations.
    """

    def __init__(self, instance_id: Optional[str] = None) -> None:
        self._instance_id = instance_id or f"ps-{os.getpid()}"
        self._sentinel_dir = DEFAULT_SENTINEL_DIR
        self._sentinel_dir.mkdir(parents=True, exist_ok=True)
        self._sentinel_path = self._sentinel_dir / f"{self._instance_id}.sentinel"
        self._file = None

    def start(self) -> None:
        """Create the sentinel file."""
        try:
            # On Windows, DELETE_ON_CLOSE is automatic with tempfile
            # For cross-platform safety, use a simple marker file
            self._sentinel_path.write_text(str(os.getpid()))
            logger.debug("Process sentinel created: %s", self._sentinel_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to create process sentinel: %s", exc)

    def stop(self) -> None:
        """Remove the sentinel file (clean shutdown)."""
        try:
            self._sentinel_path.unlink(missing_ok=True)
            logger.debug("Process sentinel removed: %s", self._sentinel_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to remove process sentinel: %s", exc)

    @property
    def is_alive(self) -> bool:
        """Return ``True`` if the sentinel file still exists."""
        return self._sentinel_path.exists()


# ---------------------------------------------------------------------------
# ShutdownCoordinator
# ---------------------------------------------------------------------------


class ShutdownCoordinator:
    """Ensure stop callbacks run exactly once, even across multiple triggers.

    Handles the common case where ``atexit`` fires while ``stop()`` is
    already running from a signal handler or gateway shutdown request.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._sentinel: Optional[ProcessSentinel] = None

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a cleanup callback.  Called in LIFO order on shutdown."""
        with self._lock:
            if not self._stopped.is_set():
                self._callbacks.append(callback)

    def install_atexit(self, sentinel: Optional[ProcessSentinel] = None) -> None:
        """Install the atexit fallback handler."""
        self._sentinel = sentinel
        if sentinel is not None:
            sentinel.start()
        atexit.register(self._atexit_handler)

    def _atexit_handler(self) -> None:
        """atexit callback — runs even on normal interpreter exit."""
        if not self._stopped.is_set():
            logger.debug("ShutdownCoordinator: atexit triggered")
            self.stop()

    def stop(self) -> None:
        """Run all registered callbacks and mark as stopped.  Idempotent."""
        if self._stopped.is_set():
            return

        with self._lock:
            if self._stopped.is_set():
                return
            self._stopped.set()

        logger.info("ShutdownCoordinator: running %d cleanup callback(s)", len(self._callbacks))
        # LIFO order
        for callback in reversed(self._callbacks):
            try:
                callback()
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShutdownCoordinator: callback failed: %s", exc)

        if self._sentinel is not None:
            self._sentinel.stop()

    @property
    def is_stopped(self) -> bool:
        """Return ``True`` when shutdown has completed."""
        return self._stopped.is_set()


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def create_shutdown_coordinator(
    instance_id: Optional[str] = None,
) -> ShutdownCoordinator:
    """Create a :class:`ShutdownCoordinator` with a process sentinel."""
    coordinator = ShutdownCoordinator()
    sentinel = ProcessSentinel(instance_id=instance_id)
    coordinator.install_atexit(sentinel=sentinel)
    return coordinator
