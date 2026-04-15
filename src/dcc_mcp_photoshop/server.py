"""PhotoshopMcpServer — MCP server for Adobe Photoshop.

Two operating modes:

**Embedded mode (default)**:
  Starts both MCP HTTP server and WebSocket bridge in one process.
  MCP clients connect to ``http://127.0.0.1:8765/mcp`` and get the full
  Photoshop tool list immediately (progressive loading via ``load_skill``).

**Gateway / bridge-only mode**:
  Use ``dcc-mcp-server.exe`` externally; this module only connects the
  WebSocket bridge via :class:`PhotoshopBridgePlugin`.

Flow (embedded mode)::

    python -m dcc_mcp_photoshop
    # MCP client connects to http://127.0.0.1:8765/mcp
    # Initial: 10 tools (6 meta + 4 stubs)
    # After load_skill("photoshop-document"): 12 tools
    # After all loaded: 26 tools (6 meta + 20 PS)

Flow (gateway mode)::

    dcc-mcp-server.exe --dcc photoshop --skill-paths ./skills --no-bridge
    python -m dcc_mcp_photoshop --bridge-only
    # MCP client connects to http://127.0.0.1:8765/mcp (direct)
    # or http://127.0.0.1:9765/mcp (gateway)
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Built-in skills directory shipped with this package
_BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"


# ---------------------------------------------------------------------------
# PhotoshopBridgePlugin — manages UXP WebSocket + HTTP RPC server
# ---------------------------------------------------------------------------


class PhotoshopBridgePlugin:
    """Minimal bridge plugin for Photoshop — manages UXP WebSocket + RPC server.

    Args:
        ws_host: Hostname for the WebSocket bridge server.
        ws_port: Port for the WebSocket bridge server (UXP connects here).
        rpc_port: Port for the HTTP RPC server (skill scripts use this).
    """

    def __init__(
        self,
        ws_host: str = "localhost",
        ws_port: int = 9001,
        rpc_port: int = 9100,
    ) -> None:
        self._ws_host = ws_host
        self._ws_port = ws_port
        self._rpc_port = rpc_port
        self._bridge = None
        self._rpc_server = None

    def connect(self) -> None:
        """Connect the WebSocket bridge (best-effort; warns on failure).

        Side-effects:
        - Sets ``DCC_MCP_PHOTOSHOP_BRIDGE_URL`` in the current process environment.
        - Writes ``~/.dcc-mcp/bridge-photoshop.json`` with the RPC endpoint URL
          so that skill scripts running inside ``dcc-mcp-server.exe`` can
          discover and call the bridge via :func:`dcc_mcp_photoshop.api.get_bridge`.
        - Starts an HTTP RPC server on ``rpc_port`` for cross-process bridge access.
        """
        from dcc_mcp_photoshop import api  # noqa: PLC0415
        from dcc_mcp_photoshop.api import BRIDGE_URL_ENV_VAR  # noqa: PLC0415
        from dcc_mcp_photoshop.api import _write_bridge_url_to_config  # noqa: PLC0415
        from dcc_mcp_photoshop.bridge import BridgeRpcServer, PhotoshopBridge  # noqa: PLC0415

        bridge = PhotoshopBridge(host=self._ws_host, port=self._ws_port)
        bridge_url = f"ws://{self._ws_host}:{self._ws_port}"
        try:
            bridge.connect()
            self._bridge = bridge
            api._bridge = bridge

            # Start HTTP RPC server for cross-process access
            self._rpc_server = BridgeRpcServer(bridge, port=self._rpc_port)
            self._rpc_server.start()

            # Publish the RPC endpoint URL for skill scripts to discover
            rpc_url = f"http://{self._ws_host}:{self._rpc_port}/rpc"
            os.environ[BRIDGE_URL_ENV_VAR] = rpc_url
            _write_bridge_url_to_config(rpc_url)
            logger.info(
                "PhotoshopBridge + RPC ready: ws=%s rpc=%s",
                bridge_url,
                rpc_url,
            )
        except Exception as exc:
            logger.warning(
                "PhotoshopBridge could not connect to %s: %s — "
                "skill calls will fail until the Photoshop UXP plugin is running",
                bridge_url,
                exc,
            )

    def disconnect(self) -> None:
        """Disconnect the bridge, stop RPC server, and clear singletons."""
        from dcc_mcp_photoshop import api  # noqa: PLC0415
        from dcc_mcp_photoshop.api import BRIDGE_URL_ENV_VAR  # noqa: PLC0415
        from dcc_mcp_photoshop.api import _remove_bridge_config  # noqa: PLC0415

        if self._rpc_server is not None:
            self._rpc_server.stop()
            self._rpc_server = None

        if self._bridge is not None:
            try:
                self._bridge.disconnect()
            except Exception as exc:
                logger.debug("PhotoshopBridge disconnect error: %s", exc)
            api._bridge = None
            self._bridge = None
            os.environ.pop(BRIDGE_URL_ENV_VAR, None)
            _remove_bridge_config()
            logger.info("PhotoshopBridge disconnected")

    @property
    def is_connected(self) -> bool:
        """Whether the bridge is currently connected."""
        return self._bridge is not None


# ---------------------------------------------------------------------------
# PhotoshopMcpServer — built on DccServerBase
# ---------------------------------------------------------------------------


class PhotoshopMcpServer:
    """MCP server for Adobe Photoshop, built on :class:`dcc_mcp_core.server_base.DccServerBase`.

    In embedded mode the MCP HTTP server and the WebSocket bridge both run in
    this process, so skill scripts can access the bridge directly via
    ``get_bridge()`` — no cross-process RPC needed.

    Args:
        port: TCP port for the MCP HTTP server.
        server_name: Name reported in MCP ``initialize`` response.
        server_version: Version reported in MCP ``initialize`` response.
        ws_host: Hostname for the UXP WebSocket bridge.
        ws_port: Port for the UXP WebSocket bridge.
        rpc_port: Port for the HTTP RPC bridge proxy (gateway mode).
        gateway_port: Gateway competition port.  ``None`` reads env var, ``0`` disables.
    """

    def __init__(
        self,
        port: int = 8765,
        server_name: str = "photoshop-mcp",
        server_version: str = "0.1.0",
        ws_host: str = "localhost",
        ws_port: int = 9001,
        rpc_port: int = 9100,
        gateway_port: int | None = None,
    ) -> None:
        from dcc_mcp_core.server_base import DccServerBase  # noqa: PLC0415

        self._base = DccServerBase(
            dcc_name="photoshop",
            builtin_skills_dir=_BUILTIN_SKILLS_DIR,
            port=port,
            server_name=server_name,
            server_version=server_version,
            gateway_port=gateway_port,
        )
        self._ws_host = ws_host
        self._ws_port = ws_port
        self._rpc_port = rpc_port
        self._gateway_port = gateway_port
        self._bridge_plugin = PhotoshopBridgePlugin(
            ws_host=ws_host, ws_port=ws_port, rpc_port=rpc_port
        )

    # ── bridge lifecycle ───────────────────────────────────────────────────

    def _connect_bridge(self) -> None:
        """Connect the WebSocket bridge (best-effort; warns on failure)."""
        self._bridge_plugin.connect()

    def _disconnect_bridge(self) -> None:
        """Disconnect the bridge and clear the module-level singleton."""
        self._bridge_plugin.disconnect()

    # ── action / skill registration ────────────────────────────────────────

    @property
    def registry(self):
        """The underlying ``ActionRegistry`` (internal; prefer ``list_skills``)."""
        return self._base.registry

    def discover_builtin_skills(
        self, extra_skill_paths: list[str] | None = None
    ) -> "PhotoshopMcpServer":
        """Discover all built-in Photoshop skills (lazy loading mode).

        This only scans for skills; it does NOT load them. Skills remain
        unloaded until explicitly requested via the ``load_skill`` meta-tool.

        Args:
            extra_skill_paths: Additional directories to scan for SKILL.md files.

        Returns:
            ``self`` for fluent chaining
        """
        paths = self._base.collect_skill_search_paths(extra_paths=extra_skill_paths)
        count = self._base._server.discover(extra_paths=paths, dcc_name="photoshop")
        logger.info(
            "SkillCatalog discovered %d skill(s) — use load_skill to load them on-demand",
            count,
        )
        return self

    def register_builtin_actions(
        self, extra_skill_paths: list[str] | None = None
    ) -> "PhotoshopMcpServer":
        """DEPRECATED: Discover and eagerly load all built-in skills.

        .. deprecated:: 0.1.0
            Use :meth:`discover_builtin_skills` for lazy loading instead.
        """
        logger.warning(
            "register_builtin_actions is deprecated; use discover_builtin_skills() "
            "for lazy loading, or switch to dcc-mcp-server.exe in gateway mode"
        )
        self._base.register_builtin_actions(extra_skill_paths=extra_skill_paths)
        return self

    # ── skill discovery helpers ────────────────────────────────────────────

    def find_skills(self, query=None, tags=None, dcc=None):
        return self._base.find_skills(query=query, tags=tags, dcc=dcc)

    def is_skill_loaded(self, name: str) -> bool:
        return self._base.is_skill_loaded(name)

    def get_skill_info(self, name: str):
        return self._base.get_skill_info(name)

    # ── capabilities ──────────────────────────────────────────────────────

    def get_capabilities(self):
        from dcc_mcp_photoshop.capabilities import photoshop_capabilities  # noqa: PLC0415

        return photoshop_capabilities()

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> Any:
        """Start the MCP HTTP server and connect the WebSocket bridge."""
        self._connect_bridge()
        return self._base.start()

    def stop(self) -> None:
        """Gracefully stop the MCP HTTP server and disconnect the bridge."""
        self._base.stop()
        self._disconnect_bridge()

    @property
    def is_running(self) -> bool:
        return self._base.is_running

    @property
    def mcp_url(self) -> Optional[str]:
        return self._base.mcp_url

    def update_gateway_metadata(self, scene=None, version=None) -> bool:
        """Update scene/version in the gateway registry."""
        return self._base.update_gateway_metadata(scene=scene, version=version)


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_server_instance: Optional[PhotoshopMcpServer] = None
_bridge_plugin: Optional[PhotoshopBridgePlugin] = None
_lock = threading.Lock()


def start_bridge_only(
    ws_host: str = "localhost", ws_port: int = 9001, rpc_port: int = 9100
) -> PhotoshopBridgePlugin:
    """Start a minimal bridge-only plugin (for use with external dcc-mcp-server).

    Args:
        ws_host: Hostname of the Photoshop UXP WebSocket server.
        ws_port: Port of the Photoshop UXP WebSocket server.
        rpc_port: Port for the HTTP RPC server (cross-process bridge access).

    Returns:
        ``PhotoshopBridgePlugin`` instance.
    """
    global _bridge_plugin
    with _lock:
        if _bridge_plugin is None:
            _bridge_plugin = PhotoshopBridgePlugin(
                ws_host=ws_host, ws_port=ws_port, rpc_port=rpc_port
            )
        if not _bridge_plugin.is_connected:
            _bridge_plugin.connect()
        return _bridge_plugin


def stop_bridge_only() -> None:
    """Stop the bridge-only plugin and disconnect from Photoshop."""
    global _bridge_plugin
    with _lock:
        if _bridge_plugin is not None:
            _bridge_plugin.disconnect()
            _bridge_plugin = None


def start_server(
    port: int = 8765,
    server_name: str = "photoshop-mcp",
    ws_host: str = "localhost",
    ws_port: int = 9001,
    rpc_port: int = 9100,
    gateway_port: int | None = None,
    register_builtins: bool = True,
    extra_skill_paths: list[str] | None = None,
) -> Any:
    """Start Photoshop MCP server in-process.

    The embedded MCP server and the WebSocket bridge both run in this process,
    so skill scripts can access the bridge directly — no cross-process RPC needed.

    Args:
        port: TCP port for the MCP HTTP server.
        server_name: Name shown in MCP ``initialize`` response.
        ws_host: Hostname of the Photoshop UXP WebSocket server.
        ws_port: Port of the Photoshop UXP WebSocket server.
        rpc_port: Port for the HTTP RPC server (used in gateway mode).
        gateway_port: Gateway competition port. ``None`` reads env var, ``0`` disables.
        register_builtins: If ``True``, discovers skills (lazy loading).
        extra_skill_paths: Additional directories to scan for ``SKILL.md`` files.

    Returns:
        ``McpServerHandle`` with ``.mcp_url()``, ``.port``, ``.shutdown()``.
    """
    global _server_instance
    with _lock:
        if _server_instance is None or not _server_instance.is_running:
            _server_instance = PhotoshopMcpServer(
                port=port,
                server_name=server_name,
                ws_host=ws_host,
                ws_port=ws_port,
                rpc_port=rpc_port,
                gateway_port=gateway_port,
            )
            if register_builtins:
                _server_instance.discover_builtin_skills(
                    extra_skill_paths=extra_skill_paths
                )
        return _server_instance.start()


def stop_server() -> None:
    """Stop the module-level singleton Photoshop MCP server."""
    global _server_instance
    with _lock:
        if _server_instance is not None:
            _server_instance.stop()
            _server_instance = None


def get_server() -> Optional[PhotoshopMcpServer]:
    """Return the current module-level singleton server instance, or ``None``."""
    return _server_instance
