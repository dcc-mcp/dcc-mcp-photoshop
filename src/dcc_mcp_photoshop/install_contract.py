"""Shared Install SOP v1 values and state paths."""

from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path

INSTALL_EXIT_OK = 0
INSTALL_EXIT_PREFLIGHT = 10
INSTALL_EXIT_ACQUIRE = 20
INSTALL_EXIT_INSTALL = 30
INSTALL_EXIT_VERIFY = 40
INSTALL_EXIT_REQUIRES_RESTART = 50
MIN_CORE_VERSION = "0.19.45"
MIN_PYTHON_VERSION = (3, 8)


def package_version(distribution: str, default: str = "unknown") -> str:
    """Return an installed distribution version without raising when absent."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return default


def version_tuple(value: str) -> tuple[int, ...]:
    """Return the leading numeric components of a version-like value."""
    parts: list[int] = []
    for part in value.split("."):
        digits = "".join(character for character in part if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def state_dir() -> Path:
    """Return the adapter-owned lifecycle state directory."""
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
