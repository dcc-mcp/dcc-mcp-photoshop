"""dcc-mcp-photoshop — Adobe Photoshop adapter for the DCC MCP ecosystem.

Migration to adobepy (v0.2.0+)
-------------------------------
Skill scripts should use ``adobepy`` facades directly::

    from adobe.dcc_mcp import action_result
    from adobe.photoshop import Photoshop

    def list_layers(**kwargs) -> dict:
        app = Photoshop()
        return action_result(
            "Listed active Photoshop layers",
            lambda: {"layers": [layer.name for layer in app.activeLayers]},
            prompt="Use the layer names in the next Photoshop operation.",
        )

Legacy helpers are still available via ``dcc_mcp_photoshop.api``::

    from dcc_mcp_photoshop.api import (
        ps_success, ps_error, ps_warning, ps_from_exception,
        get_bridge, with_photoshop,
    )

Architecture: Gateway Mode (Recommended)
-----------------------------------------
With dcc-mcp-core v0.12.23+, use the standalone server in gateway mode.
Requirements:
    - Adobe Photoshop 2022+ (UXP support)
    - adobepy >= 0.1.0
    - dcc-mcp-core >= 0.12.23
    - websockets >= 12.0
"""

from __future__ import annotations

from dcc_mcp_photoshop.__version__ import __version__
from dcc_mcp_photoshop.api import (
    Photoshop,
    PhotoshopNotAvailableError,
    action_result,
    adobe_error,
    adobe_error_context,
    adobe_exception,
    adobe_success,
    get_bridge,
    is_photoshop_available,
    photoshop_capabilities,
    ps_error,
    ps_from_exception,
    ps_success,
    ps_warning,
    recovery_suggestions,
    with_adobe,
    with_photoshop,
)
from dcc_mcp_photoshop.bridge import PhotoshopBridge
from dcc_mcp_photoshop.capabilities import PHOTOSHOP_CAPABILITIES_DICT
from dcc_mcp_photoshop.server import (
    PhotoshopBridgePlugin,
    PhotoshopMcpServer,
    get_server,
    start_bridge_only,
    start_server,
    stop_bridge_only,
    stop_server,
)

__all__ = [
    "__version__",
    "PhotoshopMcpServer",
    "start_server",
    "stop_server",
    "get_server",
    "PhotoshopBridgePlugin",
    "start_bridge_only",
    "stop_bridge_only",
    "PhotoshopBridge",
    "action_result",
    "adobe_success",
    "adobe_error",
    "adobe_exception",
    "adobe_error_context",
    "recovery_suggestions",
    "with_adobe",
    "Photoshop",
    "ps_success",
    "ps_error",
    "ps_warning",
    "ps_from_exception",
    "get_bridge",
    "is_photoshop_available",
    "with_photoshop",
    "PhotoshopNotAvailableError",
    "photoshop_capabilities",
    "PHOTOSHOP_CAPABILITIES_DICT",
]
