"""dcc-mcp-photoshop — Adobe Photoshop adapter for the DCC MCP ecosystem.

Architecture: WebSocket Bridge Mode
-------------------------------------
Photoshop does not have an embedded Python interpreter.  Instead, this package
uses a two-part architecture:

1. **UXP Plugin** (JavaScript, runs inside Photoshop):
   Opens a WebSocket server on localhost, listens for JSON-RPC 2.0 messages,
   executes Photoshop UXP API calls, and returns results.

2. **Python Bridge** (this package, runs as a standalone process):
   Connects to the UXP WebSocket server, translates MCP tool calls into
   JSON-RPC messages, and returns results to dcc-mcp-core.

Flow::

    dcc-mcp-core (MCP HTTP)  <->  PhotoshopMcpServer  <->  UXP WebSocket  <->  Photoshop

Quickstart::

    # 1. Install the UXP plugin in Photoshop (see bridge/uxp-plugin/)
    # 2. Start Photoshop — the plugin auto-starts the WebSocket server on port 3000
    # 3. Run the Python bridge:
    import dcc_mcp_photoshop
    handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=3000)
    # MCP host connects to http://127.0.0.1:8765/mcp
    handle.shutdown()

Skill authoring helpers::

    from dcc_mcp_photoshop.api import (
        ps_success, ps_error, ps_warning, ps_from_exception,
        get_bridge, with_photoshop,
    )

    @with_photoshop
    def list_layers(**kwargs) -> dict:
        bridge = get_bridge()
        layers = bridge.call("ps.listLayers")
        return ps_success(f"Found {len(layers)} layers", layers=layers)

Requirements:
    - Adobe Photoshop 2022+ (UXP support)
    - dcc-mcp-core >= 0.12.18
    - websockets >= 12.0  (used by PhotoshopBridge)
"""

from __future__ import annotations

from dcc_mcp_photoshop.__version__ import __version__
from dcc_mcp_photoshop.api import (
    PhotoshopNotAvailableError,
    get_bridge,
    is_photoshop_available,
    photoshop_capabilities,
    ps_error,
    ps_from_exception,
    ps_success,
    ps_warning,
    with_photoshop,
)
from dcc_mcp_photoshop.bridge import PhotoshopBridge
from dcc_mcp_photoshop.capabilities import PHOTOSHOP_CAPABILITIES_DICT
from dcc_mcp_photoshop.server import PhotoshopMcpServer, get_server, start_server, stop_server

__all__ = [
    "__version__",
    # Server
    "PhotoshopMcpServer",
    "start_server",
    "stop_server",
    "get_server",
    # Bridge
    "PhotoshopBridge",
    # Skill authoring helpers
    "ps_success",
    "ps_error",
    "ps_warning",
    "ps_from_exception",
    "get_bridge",
    "is_photoshop_available",
    "with_photoshop",
    "PhotoshopNotAvailableError",
    # Capabilities
    "photoshop_capabilities",
    "PHOTOSHOP_CAPABILITIES_DICT",
]
