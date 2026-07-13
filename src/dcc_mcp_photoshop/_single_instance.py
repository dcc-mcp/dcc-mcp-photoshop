"""Process-scoped lease for the machine-wide Photoshop sidecar."""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class AlreadyRunningError(RuntimeError):
    """Raised when another Photoshop sidecar owns the lease."""


def default_lock_path() -> Path:
    """Return the shared lock path, allowing an operator override."""
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_LOCK_FILE")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "dcc-mcp" / "photoshop-sidecar.lock"
    return Path.home() / ".dcc-mcp" / "photoshop-sidecar.lock"


class SingleInstanceLease:
    """Hold an OS file lock for one Photoshop sidecar process."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_lock_path()
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        """Acquire the lease without waiting."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        try:
            _lock(handle)
        except OSError as exc:
            handle.close()
            raise AlreadyRunningError(
                "dcc-mcp-photoshop is already running; reuse the registered Photoshop instance"
            ) from exc
        self._handle = handle

    def release(self) -> None:
        """Release the lease if held."""
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        with suppress(OSError):
            _unlock(handle)
        handle.close()

    def __enter__(self) -> SingleInstanceLease:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def _lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
