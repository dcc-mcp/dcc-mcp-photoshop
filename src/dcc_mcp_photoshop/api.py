"""dcc_mcp_photoshop.api — High-level Photoshop skill authoring helpers.

Unlike Maya/Blender/Unreal, Photoshop skill scripts do NOT import a DCC
module directly. Instead they use the PhotoshopBridge to communicate via
the UXP WebSocket server.

Key helpers
-----------
``ps_success(message, **context)``  — success result dict
``ps_error(message, error, **context)``  — failure result dict
``ps_from_exception(exc, ...)``  — exception to result dict
``get_bridge()``  — get the module-level bridge instance
``with_photoshop(func)``  — decorator for automatic error handling

Typical usage in a skill script::

    from dcc_mcp_photoshop.api import ps_success, ps_error, get_bridge

    def list_documents(**kwargs) -> dict:
        try:
            bridge = get_bridge()
            docs = bridge.call("ps.listDocuments")
            return ps_success(f"Found {len(docs)} document(s)", documents=docs)
        except Exception as exc:
            return ps_from_exception(exc, "Failed to list documents")
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# Module-level bridge singleton (set by PhotoshopMcpServer on startup)
_bridge = None


class PhotoshopNotAvailableError(ConnectionError):
    """Raised when the Photoshop UXP bridge is not connected."""


def is_photoshop_available() -> bool:
    """Return True if the Photoshop bridge is connected."""
    return _bridge is not None and _bridge.is_connected()


def get_bridge():
    """Return the module-level PhotoshopBridge instance.

    Raises:
        PhotoshopNotAvailableError: If bridge is not connected.
    """
    if _bridge is None or not _bridge.is_connected():
        raise PhotoshopNotAvailableError(
            "Photoshop bridge is not connected. "
            "Ensure Photoshop is running with the dcc-mcp UXP plugin and "
            "PhotoshopMcpServer.start() has been called."
        )
    return _bridge


def ps_success(message: str, *, prompt: Optional[str] = None, **context: Any) -> dict:
    """Build a success result dict compatible with ActionResultModel.

    Args:
        message: Human-readable summary of what was accomplished.
        prompt: Optional hint for the agent's next action.
        **context: Arbitrary key/value pairs (layer names, document info, etc.).

    Returns:
        dict: ActionResultModel-compatible success dict.
    """
    from dcc_mcp_core.skill import skill_success

    return skill_success(message, prompt=prompt, **context)


def ps_error(
    message: str,
    error: str,
    *,
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    **context: Any,
) -> dict:
    """Build a failure result dict compatible with ActionResultModel.

    Args:
        message: User-facing description of what went wrong.
        error: Technical error string (exception repr, error code, etc.).
        prompt: Optional recovery hint.
        possible_solutions: Optional list of actionable suggestions.
        **context: Additional context key/value pairs.
    """
    from dcc_mcp_core.skill import skill_error

    return skill_error(message, error, prompt=prompt, possible_solutions=possible_solutions, **context)


def ps_from_exception(
    exc: BaseException,
    message: Optional[str] = None,
    **context: Any,
) -> dict:
    """Build a failure result dict from a caught exception.

    Args:
        exc: The caught exception.
        message: Optional custom user-facing message.
        **context: Additional context key/value pairs.
    """
    from dcc_mcp_core.skill import skill_exception

    return skill_exception(exc, message=message, **context)


def with_photoshop(func: _F) -> _F:
    """Decorator: wrap a skill function with standard Photoshop error handling.

    Catches PhotoshopNotAvailableError and general Exception.

    Usage::

        @with_photoshop
        def list_layers(**kwargs) -> dict:
            bridge = get_bridge()
            layers = bridge.call("ps.listLayers")
            return ps_success(f"{len(layers)} layers", layers=layers)

        def main(**kwargs):
            return list_layers(**kwargs)
    """

    @functools.wraps(func)
    def wrapper(**kwargs: Any) -> dict:
        try:
            return func(**kwargs)
        except PhotoshopNotAvailableError as exc:
            return ps_error(
                "Photoshop is not available — bridge not connected",
                repr(exc),
                prompt="Ensure Photoshop is running with the dcc-mcp UXP plugin installed and active.",
                possible_solutions=[
                    "Install the dcc-mcp UXP plugin from bridge/uxp-plugin/",
                    "Start Photoshop before launching the MCP server",
                    "Check the WebSocket port (default: 3000) is not blocked",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Skill execution failed: %s", func.__name__)
            return ps_from_exception(exc)

    return wrapper  # type: ignore[return-value]
