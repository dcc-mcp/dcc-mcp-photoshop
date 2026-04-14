"""dcc-mcp-photoshop — Adobe Photoshop adapter for the DCC MCP ecosystem.

Architecture: Gateway Mode (Recommended, v0.1.0+)
--------------------------------------------------
With dcc-mcp-core v0.12.23+, use the standalone server in gateway mode:

1. Start dcc-mcp-server.exe with Photoshop skills::

    dcc-mcp-server.exe --dcc photoshop --skill-paths ./src/dcc_mcp_photoshop/skills

2. Start the bridge plugin to maintain UXP connection::

    import dcc_mcp_photoshop
    bridge = dcc_mcp_photoshop.start_bridge_only(ws_port=9001)
    # Skills are loaded progressively on demand
    # MCP client connects to http://127.0.0.1:8765/mcp

Benefits:
  - Progressive skill loading (smaller initial tool list)
  - Better scalability (separate server process)
  - No eager loading of all tools

Legacy Architecture: Embedded Server (Deprecated)
--------------------------------------------------
For backwards compatibility, you can still use the embedded mode::

    import dcc_mcp_photoshop
    handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=9001)
    # All skills are eagerly loaded at startup (not recommended)
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
    - dcc-mcp-core >= 0.12.23
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
    # Server (legacy embedded mode — deprecated)
    "PhotoshopMcpServer",
    "start_server",
    "stop_server",
    "get_server",
    # Bridge (gateway mode — recommended)
    "PhotoshopBridgePlugin",
    "start_bridge_only",
    "stop_bridge_only",
    # Bridge protocol
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
