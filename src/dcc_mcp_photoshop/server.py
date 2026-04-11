"""PhotoshopMcpServer — MCP bridge server for Adobe Photoshop.

Architecture (bridge mode, not embedded):

    MCP Client (Claude/Cursor)
         | HTTP (MCP Streamable HTTP)
    PhotoshopMcpServer (this class, port 8765)
         | registers action handlers that use PhotoshopBridge
    PhotoshopBridge (WebSocket client, port 3000)
         | JSON-RPC over WebSocket
    Photoshop UXP Plugin (JavaScript WebSocket server)
         | Photoshop UXP API calls
    Adobe Photoshop

The DccCapabilities for Photoshop explicitly marks:
    has_embedded_python = False
    bridge_kind = "websocket"
    bridge_endpoint = "ws://localhost:3000"
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

_BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"

_server_instance: Optional["PhotoshopMcpServer"] = None
_server_lock = threading.Lock()


class PhotoshopMcpServer:
    """MCP bridge server for Adobe Photoshop.

    Uses WebSocket bridge mode: skills call bridge.call() instead of
    importing a DCC Python module directly.
    """

    def __init__(
        self,
        port: int = 8765,
        ws_host: str = "localhost",
        ws_port: int = 3000,
        extra_skill_paths: Optional[List[str]] = None,
    ) -> None:
        self._port = port
        self._ws_host = ws_host
        self._ws_port = ws_port
        self._extra_skill_paths = extra_skill_paths or []
        self._server = None
        self._handle = None
        self._bridge = None

    def _get_skill_paths(self) -> List[str]:
        """Resolve skill paths in priority order."""
        paths: List[str] = []
        paths.extend(self._extra_skill_paths)
        if _BUILTIN_SKILLS_DIR.exists():
            paths.append(str(_BUILTIN_SKILLS_DIR))
        return paths

    def _init_bridge(self) -> None:
        """Initialize and connect the WebSocket bridge."""
        from dcc_mcp_photoshop import api
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        self._bridge = PhotoshopBridge(host=self._ws_host, port=self._ws_port)
        try:
            self._bridge.connect()
            api._bridge = self._bridge
            logger.info("PhotoshopBridge connected to ws://%s:%d", self._ws_host, self._ws_port)
        except Exception as exc:
            logger.warning(
                "PhotoshopBridge could not connect to ws://%s:%d: %s — "
                "skill calls will fail until Photoshop UXP plugin is running",
                self._ws_host,
                self._ws_port,
                exc,
            )

    def register_builtin_actions(self) -> None:
        """Discover and load all built-in Photoshop skills."""
        from dcc_mcp_core import McpHttpConfig, create_skill_manager

        config = McpHttpConfig(port=self._port)
        extra_paths = self._get_skill_paths()
        self._server = create_skill_manager(
            "photoshop",
            config=config,
            extra_paths=extra_paths or None,
            dcc_name="photoshop",
        )
        logger.info("PhotoshopMcpServer: registered skills from %d path(s)", len(extra_paths))

    def start(self) -> Any:
        """Start the MCP HTTP server and connect the bridge.

        Returns:
            ServerHandle — call .mcp_url() and .shutdown() on it.
        """
        self._init_bridge()
        if self._server is None:
            self.register_builtin_actions()
        self._handle = self._server.start()
        logger.info("PhotoshopMcpServer started at %s", self._handle.mcp_url())
        return self._handle

    def stop(self) -> None:
        """Stop the MCP HTTP server and disconnect the bridge."""
        if self._handle is not None:
            self._handle.shutdown()
            self._handle = None
        if self._bridge is not None:
            self._bridge.disconnect()
            self._bridge = None
        logger.info("PhotoshopMcpServer stopped")


def start_server(
    port: int = 8765,
    ws_host: str = "localhost",
    ws_port: int = 3000,
    extra_skill_paths: Optional[List[str]] = None,
) -> Any:
    """Start the module-level singleton MCP server for Photoshop.

    Thread-safe. If already running, returns the existing handle.

    Args:
        port: MCP HTTP port (default 8765).
        ws_host: Photoshop UXP WebSocket host (default "localhost").
        ws_port: Photoshop UXP WebSocket port (default 3000).
        extra_skill_paths: Additional skill directories to load.

    Returns:
        ServerHandle with .mcp_url() and .shutdown() methods.
    """
    global _server_instance
    with _server_lock:
        if _server_instance is None:
            _server_instance = PhotoshopMcpServer(
                port=port,
                ws_host=ws_host,
                ws_port=ws_port,
                extra_skill_paths=extra_skill_paths,
            )
        return _server_instance.start()


def stop_server() -> None:
    """Stop the module-level singleton MCP server."""
    global _server_instance
    with _server_lock:
        if _server_instance is not None:
            _server_instance.stop()
            _server_instance = None
