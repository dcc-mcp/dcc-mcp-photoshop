"""Shared Install SOP v1 values and state paths."""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path

INSTALL_EXIT_OK = 0
INSTALL_EXIT_PREFLIGHT = 10
INSTALL_EXIT_ACQUIRE = 20
INSTALL_EXIT_INSTALL = 30
INSTALL_EXIT_VERIFY = 40
INSTALL_EXIT_REQUIRES_RESTART = 50
MIN_CORE_VERSION = "0.20.14"
MIN_PYTHON_VERSION = (3, 8)
INSTALL_SOP_SCHEMA_ID = "https://dcc-mcp.github.io/schemas/adapter-install-sop-v1.schema.json"
INSTALL_SOP_SCHEMA_SIZE = 4_261
INSTALL_SOP_SCHEMA_SHA256 = "3ca25788439917b4d4c0617230a762f9797756b5b54f45c8c4149f975b90f904"
_MAX_VERSION_LENGTH = 39
_FINAL_RELEASE_VERSION = re.compile(
    r"(0|[1-9][0-9]{0,8})(?:\.(0|[1-9][0-9]{0,8}))?"
    r"(?:\.(0|[1-9][0-9]{0,8}))?(?:\.(0|[1-9][0-9]{0,8}))?"
)


def package_version(distribution: str, default: str = "unknown") -> str:
    """Return an installed distribution version without raising when absent."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return default


def version_tuple(value: str) -> tuple[int, ...]:
    """Return bounded numeric components for a final-release version."""
    if not isinstance(value, str) or not value or len(value) > _MAX_VERSION_LENGTH:
        return ()
    match = _FINAL_RELEASE_VERSION.fullmatch(value)
    if match is None:
        return ()
    return tuple(int(part) for part in match.groups() if part is not None)


def state_dir() -> Path:
    """Return the adapter-owned lifecycle state directory."""
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
