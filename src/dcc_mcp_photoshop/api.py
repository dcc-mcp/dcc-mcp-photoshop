"""dcc_mcp_photoshop.api — High-level Photoshop skill authoring helpers.

Migrated to ``adobepy`` facade and ``adobe.dcc_mcp`` result helpers
(v0.2.0+).  Skill scripts should use ``Photoshop()`` sessions and
``action_result()`` directly.  Legacy ``ps_*`` wrappers are kept for
backward compatibility.

New-style skill (recommended)::

    from adobe.dcc_mcp import action_result
    from adobe.photoshop import Photoshop

    def list_layers(**kwargs) -> dict:
        app = Photoshop()
        return action_result(
            "Listed active Photoshop layers",
            lambda: {"layers": [layer.name for layer in app.activeLayers]},
            prompt="Use the layer names in the next Photoshop operation.",
        )

Legacy compat (deprecated — still works)::

    from dcc_mcp_photoshop.api import ps_success, get_bridge, with_photoshop

    @with_photoshop
    def list_layers(**kwargs) -> dict:
        bridge = get_bridge()
        layers = bridge.call("ps.listLayers")
        return ps_success(f"Found {len(layers)} layers", layers=layers)
"""

from __future__ import annotations

import functools
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# Module-level bridge singleton (set by PhotoshopMcpServer on startup)
# Kept for backward-compatible get_bridge() path.
_bridge = None

# Environment variable key used by the bridge to publish its WebSocket URL
# so that child processes (e.g. skill scripts running under dcc-mcp-server)
# can discover the bridge via os.environ or dcc_mcp_photoshop.api.get_bridge().
BRIDGE_URL_ENV_VAR = "DCC_MCP_PHOTOSHOP_BRIDGE_URL"

_BRIDGE_CONFIG_PATH = os.path.expanduser("~/.dcc-mcp/bridge-photoshop.json")


def _write_bridge_url_to_config(rpc_url: str) -> None:
    """Write the RPC endpoint URL to the bridge config file.

    Skill scripts running inside ``dcc-mcp-server.exe`` read this file
    to discover the bridge's RPC endpoint for cross-process access.
    """
    config = {}
    if os.path.isfile(_BRIDGE_CONFIG_PATH):
        try:
            with open(_BRIDGE_CONFIG_PATH) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    config["dcc_type"] = "photoshop"
    config["bridge_url"] = rpc_url
    os.makedirs(os.path.dirname(_BRIDGE_CONFIG_PATH), exist_ok=True)
    with open(_BRIDGE_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _remove_bridge_config() -> None:
    """Remove the bridge config file."""
    try:
        os.remove(_BRIDGE_CONFIG_PATH)
    except FileNotFoundError:
        pass
    except OSError:
        logger.debug("Failed to remove bridge config: %s", _BRIDGE_CONFIG_PATH)


# ---------------------------------------------------------------------------
# New adobepy-backed helpers (v0.2.0+)
# ---------------------------------------------------------------------------

# Import from adobe.dcc_mcp — these are the canonical result helpers.
# They delegate to dcc_mcp_core.skill when available; otherwise return
# plain dicts for tests/docs.
from adobe.dcc_mcp import (  # noqa: E402, F401
    action_result,
    adobe_error,
    adobe_error_context,
    adobe_exception,
    adobe_success,
    recovery_suggestions,
    with_adobe,
)

# Import Photoshop facade for direct use by skill scripts.
from adobe.photoshop import Photoshop  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class PhotoshopNotAvailableError(ConnectionError):
    """Raised when the Photoshop UXP bridge is not connected."""


# ---------------------------------------------------------------------------
# Bridge access helpers (deprecated — use Photoshop() facade)
# ---------------------------------------------------------------------------


def is_photoshop_available() -> bool:
    """Return ``True`` if the Photoshop bridge is connected.

    .. deprecated:: 0.2.0
        Use ``Photoshop()`` session directly; connection state is managed
        by the adobepy broker.
    """
    return _bridge is not None and _bridge.is_connected()


def get_bridge():
    """Return the module-level ``PhotoshopBridge`` instance.

    .. deprecated:: 0.2.0
        New skills should construct ``Photoshop()`` sessions directly.
        The bridge path is kept for backward compatibility only.

    Raises:
        PhotoshopNotAvailableError: When the bridge is not connected.
    """
    if _bridge is None or not _bridge.is_connected():
        raise PhotoshopNotAvailableError(
            "Photoshop bridge is not connected. "
            "Ensure Photoshop is running with the dcc-mcp UXP plugin and "
            "start_server() has been called."
        )
    return _bridge


# ---------------------------------------------------------------------------
# Legacy result helpers (backward-compatible wrappers)
# ---------------------------------------------------------------------------


def ps_success(message: str, prompt: Optional[str] = None, **context: Any) -> Dict[str, Any]:
    """Return a success result dict (backward-compatible wrapper).

    .. deprecated:: 0.2.0
        Prefer ``adobe.dcc_mcp.action_result()`` or
        ``adobe.dcc_mcp.adobe_success()`` directly.
    """
    return adobe_success(message, prompt=prompt, **context)


def ps_error(
    message: str,
    error: str = "",
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    **context: Any,
) -> Dict[str, Any]:
    """Return a failure result dict (backward-compatible wrapper).

    .. deprecated:: 0.2.0
        Prefer ``adobe.dcc_mcp.adobe_error()`` or
        ``adobe.dcc_mcp.adobe_exception()`` directly.
    """
    return adobe_error(
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
    """Return a success dict with a non-fatal warning note (backward-compatible).

    .. deprecated:: 0.2.0
        Include a ``warning`` key in your ``action_result()`` context directly.
    """
    context.setdefault("warning", warning)
    return adobe_success(message, prompt=prompt, **context)


def ps_from_exception(
    exc: BaseException,
    message: str = "Photoshop operation failed",
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    include_traceback: bool = True,
    **context: Any,
) -> Dict[str, Any]:
    """Return a failure result from an exception (backward-compatible wrapper).

    .. deprecated:: 0.2.0
        Prefer ``adobe.dcc_mcp.adobe_exception()`` directly.
    """
    return adobe_exception(
        exc,
        message=message,
        prompt=prompt,
        possible_solutions=possible_solutions,
        include_traceback=include_traceback,
        **context,
    )


# ---------------------------------------------------------------------------
# Decorator (backward-compatible wrapper)
# ---------------------------------------------------------------------------

_PS_NOT_AVAILABLE_MSG = "Photoshop not available"
_PS_NOT_AVAILABLE_SOLUTIONS = [
    "Install the dcc-mcp UXP plugin from bridge/uxp-plugin/",
    "Start Photoshop before launching the MCP server",
    "Check that the WebSocket port (default: 3000) is not blocked by a firewall",
    "Call start_server() to initialise the bridge connection",
]


def with_photoshop(func: _F) -> _F:
    """Decorator for Photoshop error handling (backward-compatible wrapper).

    .. deprecated:: 0.2.0
        Prefer ``adobe.dcc_mcp.with_adobe()`` which maps adobepy errors
        (BrokerConnectionError, HostNotRunningError, etc.) directly.
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
                message=f"Failed to execute {func.__name__}",
            )

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------

__all__ = [
    # New adobepy result helpers (recommended)
    "action_result",
    "adobe_success",
    "adobe_error",
    "adobe_exception",
    "adobe_error_context",
    "recovery_suggestions",
    "with_adobe",
    # New adobepy session
    "Photoshop",
    # Legacy result helpers (deprecated)
    "ps_success",
    "ps_error",
    "ps_warning",
    "ps_from_exception",
    # Legacy bridge helpers (deprecated)
    "get_bridge",
    "is_photoshop_available",
    # Legacy decorator (deprecated)
    "with_photoshop",
    # Constants
    "BRIDGE_URL_ENV_VAR",
    # Exception types
    "PhotoshopNotAvailableError",
    # Capabilities
    "photoshop_capabilities",
]

# Import photoshop_capabilities so it is accessible as dcc_mcp_photoshop.api.photoshop_capabilities
from dcc_mcp_photoshop.capabilities import photoshop_capabilities  # noqa: E402, F401
