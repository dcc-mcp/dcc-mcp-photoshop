"""Shared Install SOP v1 values and state paths."""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

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
_MAX_VERSION_LENGTH = 39
_MAX_SCHEMA_SIZE = 16_777_216
_SHA256_HEX_LENGTH = 64
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


def satisfies_core_specifier(value: str) -> bool:
    """Return whether a final Core version satisfies the adapter's bounds."""
    parsed = version_tuple(value)
    if not parsed:
        return False
    normalized = parsed + (0,) * (3 - len(parsed))
    minimum = version_tuple(MIN_CORE_VERSION) + (0,) * (3 - len(version_tuple(MIN_CORE_VERSION)))
    maximum = version_tuple(MAX_CORE_VERSION_EXCLUSIVE) + (0,) * (3 - len(version_tuple(MAX_CORE_VERSION_EXCLUSIVE)))
    return minimum <= normalized < maximum


def satisfies_adobepy_specifier(value: str) -> bool:
    """Return whether a final adobepy SDK version matches the pinned runtime."""
    return version_tuple(value) == version_tuple("0.6.2")


class CoreSchemaAnchor(NamedTuple):
    """Measured byte identity of one published revision of the Core Install SOP schema."""

    size: int
    sha256: str


# Core republishes `adapter-install-sop-v1.schema.json` under the same `-v1` revision id, so
# its byte identity is a function of the Core release rather than a constant of the contract.
# Key each measured revision by the first Core release that shipped it and append new rows;
# editing an existing row would silently re-pin a digest that was already published.
CORE_SCHEMA_ANCHORS: Tuple[Tuple[Tuple[int, int, int], CoreSchemaAnchor], ...] = (
    ((0, 20, 14), CoreSchemaAnchor(4_261, "3ca25788439917b4d4c0617230a762f9797756b5b54f45c8c4149f975b90f904")),
    ((0, 20, 30), CoreSchemaAnchor(4_899, "2b3a8a101384a5163c7569c4a2b0de6586c672c5ee291735f94334a33b7d37a0")),
)

# Highest Core release whose schema bytes were measured into CORE_SCHEMA_ANCHORS. A newer Core
# release verifies without a pinned digest instead of failing, so a Core release can never
# strand an installed adapter; add its row here (and bump this floor) once it is measured.
CORE_SCHEMA_ANCHOR_MEASURED_THROUGH = "0.20.33"


def core_schema_anchor(core_version: str) -> Optional[CoreSchemaAnchor]:
    """Return the measured Core Install SOP schema identity for a Core version.

    Callers must apply `satisfies_core_specifier` first. Returns `None` for versions this
    adapter has not measured yet, which is the forward-compatible path for new Core releases.
    """
    parsed = version_tuple(core_version)
    if not parsed:
        return None
    normalized = parsed + (0,) * (3 - len(parsed))
    if normalized > version_tuple(CORE_SCHEMA_ANCHOR_MEASURED_THROUGH):
        return None
    anchor: Optional[CoreSchemaAnchor] = None
    for floor, candidate in CORE_SCHEMA_ANCHORS:
        if normalized >= floor:
            anchor = candidate
    return anchor


def core_schema_identity_is_bounded(identity: object) -> bool:
    """Return whether a reported Core schema size/sha256 pair is safe to compare."""
    if not isinstance(identity, dict):
        return False
    size = identity.get("size")
    digest = identity.get("sha256")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= _MAX_SCHEMA_SIZE:
        return False
    return isinstance(digest, str) and len(digest) == _SHA256_HEX_LENGTH


def state_dir() -> Path:
    """Return the adapter-owned lifecycle state directory."""
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
