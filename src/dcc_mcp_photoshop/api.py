"""dcc_mcp_photoshop.api — High-level Photoshop skill authoring helpers.

Unlike Maya/Blender/Unreal, Photoshop skill scripts do NOT import a DCC
Python module directly.  Instead they use the PhotoshopBridge to communicate
via the UXP WebSocket server.

Key helpers
-----------
``ps_success(message, **context)``
    Build a success result dict backed by ``dcc_mcp_core.skill.skill_success``.

``ps_error(message, error, **context)``
    Build a failure ActionResultModel dict.

``ps_warning(message, warning, **context)``
    Build a success dict that carries a non-fatal warning note.

``ps_from_exception(exc, message, **context)``
    Build a failure dict from a caught exception, including the full traceback.

``get_bridge()``
    Return the module-level ``PhotoshopBridge`` instance; raises
    ``PhotoshopNotAvailableError`` when the bridge is not connected.

``is_photoshop_available()``
    Return ``True`` if the bridge is connected.

``with_photoshop(func)``
    Decorator that wraps the entire function body in the standard
    try/PhotoshopNotAvailableError/Exception pattern.

Typical usage in a skill script::

    from dcc_mcp_photoshop.api import ps_success, ps_error, get_bridge, with_photoshop

    @with_photoshop
    def list_layers(**kwargs) -> dict:
        bridge = get_bridge()
        layers = bridge.call("ps.listLayers")
        return ps_success(f"Found {len(layers)} layers", layers=layers)
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# Module-level bridge singleton (set by PhotoshopMcpServer on startup)
_bridge = None


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class PhotoshopNotAvailableError(ConnectionError):
    """Raised when the Photoshop UXP bridge is not connected."""


# ---------------------------------------------------------------------------
# Bridge access helpers
# ---------------------------------------------------------------------------


def is_photoshop_available() -> bool:
    """Return ``True`` if the Photoshop bridge is connected.

    Example::

        if is_photoshop_available():
            bridge = get_bridge()
    """
    return _bridge is not None and _bridge.is_connected()


def get_bridge():
    """Return the module-level ``PhotoshopBridge`` instance.

    Raises:
        PhotoshopNotAvailableError: When the bridge is not connected.

    Example::

        bridge = get_bridge()
        result = bridge.call("ps.getDocumentInfo")
    """
    if _bridge is None or not _bridge.is_connected():
        raise PhotoshopNotAvailableError(
            "Photoshop bridge is not connected. "
            "Ensure Photoshop is running with the dcc-mcp UXP plugin and "
            "start_server() has been called."
        )
    return _bridge


# ---------------------------------------------------------------------------
# Core result helpers
# ---------------------------------------------------------------------------


def ps_success(message: str, prompt: Optional[str] = None, **context: Any) -> Dict[str, Any]:
    """Return a success ActionResultModel as a plain dict.

    Thin wrapper around ``dcc_mcp_core.skill.skill_success`` so skill scripts
    do not need to import from two packages.

    Args:
        message: Human-readable success message.
        prompt: Optional follow-up hint shown to the AI agent.
        **context: Arbitrary key/value pairs stored in ``result["context"]``.

    Returns:
        Serialised ``ActionResultModel`` dict (``success=True``).

    Example::

        return ps_success("Got document info", name=doc_name, width=width)
    """
    from dcc_mcp_core.skill import skill_success  # noqa: PLC0415

    return skill_success(message, prompt=prompt, **context)


def ps_error(
    message: str,
    error: str = "",
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    **context: Any,
) -> Dict[str, Any]:
    """Return a failure ActionResultModel as a plain dict.

    Args:
        message: Short human-readable description of what went wrong.
        error: Detailed error string (e.g. exception message or error code).
        prompt: Optional follow-up hint shown to the AI agent.
        possible_solutions: List of actionable fix suggestions.
        **context: Arbitrary key/value pairs stored in ``result["context"]``.

    Returns:
        Serialised ``ActionResultModel`` dict (``success=False``).

    Example::

        return ps_error(
            "Document not found",
            "No active document in Photoshop",
            possible_solutions=["Open a document in Photoshop first"],
        )
    """
    from dcc_mcp_core.skill import skill_error  # noqa: PLC0415

    return skill_error(
        message,
        error,
        prompt=prompt,
        possible_solutions=possible_solutions,
        **context,
    )


def ps_warning(
    message: str,
    warning: str = "",
    prompt: Optional[str] = None,
    **context: Any,
) -> Dict[str, Any]:
    """Return a success ActionResultModel dict with a non-fatal warning note.

    The result is a *success* (``success=True``) but includes a ``warning``
    key to inform the AI agent of a non-fatal issue.

    Corresponds to ``dcc_mcp_core.skill.skill_warning``.

    Args:
        message: Human-readable success message.
        warning: Short description of the non-fatal warning.
        prompt: Optional follow-up hint shown to the AI agent.
        **context: Arbitrary key/value pairs stored in ``result["context"]``.

    Returns:
        Serialised ``ActionResultModel`` dict (``success=True``, with
        ``context["warning"]`` set).

    Example::

        return ps_warning(
            "Layer renamed with fallback",
            warning="Special characters stripped from layer name",
            layer_name="Background",
        )
    """
    from dcc_mcp_core.skill import skill_warning  # noqa: PLC0415

    return skill_warning(message, warning=warning, prompt=prompt, **context)


def ps_from_exception(
    exc: BaseException,
    message: str = "Photoshop operation failed",
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    include_traceback: bool = True,
    **context: Any,
) -> Dict[str, Any]:
    """Return a failure ActionResultModel from a live exception.

    Unlike ``ps_error("...", str(exc))``, this captures the full traceback
    and passes it to the agent for richer diagnostics.

    Args:
        exc: The caught exception.
        message: Short description of the failed operation.
        prompt: Optional follow-up hint shown to the AI agent.
        possible_solutions: List of actionable fix suggestions.
        include_traceback: Whether to include the full traceback (default ``True``).
        **context: Arbitrary key/value pairs stored in ``result["context"]``.

    Returns:
        Serialised ``ActionResultModel`` dict (``success=False``).

    Example::

        except Exception as exc:
            logger.exception("list_layers failed")
            return ps_from_exception(exc, "Failed to list layers")
    """
    from dcc_mcp_core.skill import skill_exception  # noqa: PLC0415

    return skill_exception(
        exc,
        message=message,
        prompt=prompt,
        include_traceback=include_traceback,
        possible_solutions=possible_solutions,
        **context,
    )


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

_PS_NOT_AVAILABLE_MSG = "Photoshop not available"
_PS_NOT_AVAILABLE_SOLUTIONS = [
    "Install the dcc-mcp UXP plugin from bridge/uxp-plugin/",
    "Start Photoshop before launching the MCP server",
    "Check that the WebSocket port (default: 3000) is not blocked by a firewall",
    "Call start_server() to initialise the bridge connection",
]


def with_photoshop(func: _F) -> _F:
    """Decorator that wraps a skill function with the standard Photoshop error pattern.

    The decorated function is called normally.  Any exception is caught and
    converted to an ``ActionResultModel`` error dict:

    * ``PhotoshopNotAvailableError`` → ``ps_error("Photoshop not available", ...)``
    * Any other ``Exception``        → ``ps_from_exception(exc, ...)``

    Example::

        from dcc_mcp_photoshop.api import with_photoshop, ps_success

        @with_photoshop
        def list_layers(**kwargs) -> dict:
            bridge = get_bridge()
            layers = bridge.call("ps.listLayers")
            return ps_success(f"Found {len(layers)} layers", layers=layers)

    .. note::
        The decorator does **not** log exceptions itself.  Add a
        ``logger.exception(...)`` call before ``return ps_from_exception``
        if you need structured logging.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            return func(*args, **kwargs)
        except PhotoshopNotAvailableError as exc:
            return ps_error(
                _PS_NOT_AVAILABLE_MSG,
                repr(exc),
                possible_solutions=_PS_NOT_AVAILABLE_SOLUTIONS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            return ps_from_exception(
                exc,
                message="Failed to execute {}".format(func.__name__),
            )

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------

__all__ = [
    # Result helpers
    "ps_success",
    "ps_error",
    "ps_warning",
    "ps_from_exception",
    # Bridge helpers
    "get_bridge",
    "is_photoshop_available",
    # Decorator
    "with_photoshop",
    # Exception types
    "PhotoshopNotAvailableError",
    # Capabilities
    "photoshop_capabilities",
]

# Import photoshop_capabilities so it is accessible as dcc_mcp_photoshop.api.photoshop_capabilities
from dcc_mcp_photoshop.capabilities import photoshop_capabilities  # noqa: E402, F401
