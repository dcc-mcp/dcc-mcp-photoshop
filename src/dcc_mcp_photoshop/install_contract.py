"""Shared Install SOP v1 values and state paths."""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

INSTALL_EXIT_OK = 0
INSTALL_EXIT_PREFLIGHT = 10
INSTALL_EXIT_ACQUIRE = 20
INSTALL_EXIT_INSTALL = 30
INSTALL_EXIT_VERIFY = 40
INSTALL_EXIT_REQUIRES_RESTART = 50
MIN_CORE_VERSION = "0.20.14"
MAX_CORE_VERSION_EXCLUSIVE = "0.21.0"
CORE_SPECIFIER = ">=0.20.14,<0.21.0"
ADOBEPY_SPECIFIER = "==0.6.2"
MIN_PYTHON_VERSION = (3, 8)
INSTALL_SOP_SCHEMA_ID = "https://dcc-mcp.github.io/schemas/adapter-install-sop-v1.schema.json"
# Digests of the Install SOP v1 schema shipped by Core, keyed by the first Core version
# that published each digest. The adapter resolves the anchor from the installed Core
# version instead of pinning one literal, so a Core release that leaves the schema
# untouched passes unchanged while an in-place rewrite of an immutable `-v1` artifact is
# still detected. Append a new entry when Core legitimately ships a new revision.
INSTALL_SOP_SCHEMA_ANCHORS: Tuple[Tuple[str, int, str], ...] = (
    ("0.20.30", 4_899, "2b3a8a101384a5163c7569c4a2b0de6586c672c5ee291735f94334a33b7d37a0"),
    ("0.20.14", 4_261, "3ca25788439917b4d4c0617230a762f9797756b5b54f45c8c4149f975b90f904"),
)
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


def _padded_version(value: str) -> tuple[int, int, int]:
    """Return a three-component version tuple, padded with zeros when shorter."""
    parsed = version_tuple(value)
    if not parsed:
        return ()
    return parsed + (0,) * (3 - len(parsed))  # type: ignore[return-value]


def satisfies_core_specifier(value: str) -> bool:
    """Return whether a final Core version satisfies the adapter's bounds."""
    normalized = _padded_version(value)
    if not normalized:
        return False
    minimum = _padded_version(MIN_CORE_VERSION)
    maximum = _padded_version(MAX_CORE_VERSION_EXCLUSIVE)
    return minimum <= normalized < maximum


def expected_core_schema_anchor(core_version: Any) -> Optional[Dict[str, Any]]:
    """Return the Install SOP schema anchor in force for an installed Core version.

    The anchor is selected by Core version rather than hardcoded as a single literal, so
    the adapter stays correct across Core releases. A Core version newer than every
    recorded anchor uses the newest anchor, which keeps the check green while the schema
    is unchanged and still fails closed when Core rewrites it in place.
    """
    if not isinstance(core_version, str):
        return None
    parsed = _padded_version(core_version)
    if not parsed:
        return None
    for since_version, size, sha256 in INSTALL_SOP_SCHEMA_ANCHORS:
        if parsed >= _padded_version(since_version):
            return {"since": since_version, "size": size, "sha256": sha256}
    return None


def satisfies_adobepy_specifier(value: str) -> bool:
    """Return whether a final adobepy SDK version matches the pinned runtime."""
    return version_tuple(value) == version_tuple("0.6.2")


def state_dir() -> Path:
    """Return the adapter-owned lifecycle state directory."""
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
