"""PhotoshopMcpServer — MCP bridge server for Adobe Photoshop.

Architecture (bridge mode — Photoshop has no embedded Python)::

    MCP Client (Claude Desktop / Cursor / …)
         │ HTTP  (MCP Streamable HTTP, 2025-03-26 spec)
    PhotoshopMcpServer  (this class, default port 8765)
         │ uses dcc-mcp-core create_skill_manager
         │ skill scripts call get_bridge() → PhotoshopBridge
    PhotoshopBridge  (WebSocket client, Python WS server port 9001 (UXP connects here))
         │ JSON-RPC 2.0 over WebSocket
    Photoshop UXP Plugin  (JavaScript WebSocket server)
         │ UXP API calls
    Adobe Photoshop

Skills-First API (dcc-mcp-core v0.12.12+)
------------------------------------------
The preferred entry point is :func:`create_skill_manager` from ``dcc-mcp-core``,
which wires up ``ActionRegistry``, ``ActionDispatcher``, ``SkillCatalog`` and
auto-discovers skills from env vars in one call.

:class:`PhotoshopMcpServer` wraps this factory and adds Photoshop-specific
path discovery so built-in skills shipped with this package are always
included, and also manages the WebSocket bridge lifecycle.

Flow::

    server = PhotoshopMcpServer(port=8765)
    server.register_builtin_actions()   # discover & load all skills
    handle = server.start()
    print(handle.mcp_url())             # http://127.0.0.1:8765/mcp
    handle.shutdown()

Or via the module-level singleton helper::

    import dcc_mcp_photoshop
    handle = dcc_mcp_photoshop.start_server(port=8765)
    print(handle.mcp_url())

Search path resolution (highest → lowest priority):

1. ``extra_skill_paths`` supplied by the caller
2. Built-in skills shipped with this package  (``src/dcc_mcp_photoshop/skills/``)
3. ``DCC_MCP_PHOTOSHOP_SKILL_PATHS`` environment variable  (Photoshop-specific)
4. ``DCC_MCP_SKILL_PATHS`` environment variable  (global fallback)
5. Platform default  (``dcc_mcp_core.get_skills_dir()``)
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Built-in skills directory shipped with this package
_BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"


# ---------------------------------------------------------------------------
# Skills search path helpers
# ---------------------------------------------------------------------------


def _collect_skill_search_paths(extra_paths: Optional[List[str]] = None) -> List[str]:
    """Build the ordered skill search path list.

    Priority (highest first):

    1. ``extra_paths`` supplied by the caller
    2. Built-in skills directory (``src/dcc_mcp_photoshop/skills/``)
    3. ``DCC_MCP_PHOTOSHOP_SKILL_PATHS`` — Photoshop-specific env var
    4. ``DCC_MCP_SKILL_PATHS`` — global fallback env var
    5. Platform default skills dir (``get_skills_dir()``)
    """
    from dcc_mcp_core import get_app_skill_paths_from_env, get_skill_paths_from_env, get_skills_dir  # noqa: PLC0415

    paths: List[str] = list(extra_paths or [])

    if _BUILTIN_SKILLS_DIR.is_dir():
        paths.append(str(_BUILTIN_SKILLS_DIR))

    # Per-app env var: DCC_MCP_PHOTOSHOP_SKILL_PATHS
    paths.extend(get_app_skill_paths_from_env("photoshop"))

    # Global fallback env var: DCC_MCP_SKILL_PATHS
    paths.extend(get_skill_paths_from_env())

    default_dir = get_skills_dir()
    if default_dir and default_dir not in paths:
        paths.append(default_dir)

    return paths


# ---------------------------------------------------------------------------
# PhotoshopMcpServer
# ---------------------------------------------------------------------------


class PhotoshopMcpServer:
    """MCP Streamable HTTP server for Adobe Photoshop (bridge mode).

    Uses the Skills-First API introduced in dcc-mcp-core v0.12.12:
    :func:`dcc_mcp_core.create_skill_manager` wires up the full stack
    (registry, dispatcher, catalog) in one call.

    In addition to the standard MCP server lifecycle, this class manages
    the ``PhotoshopBridge`` WebSocket connection so skill scripts can call
    ``get_bridge()`` at any point after ``start()`` is called.

    Example::

        server = PhotoshopMcpServer(port=8765)
        server.register_builtin_actions()
        handle = server.start()
        print(handle.mcp_url())   # http://127.0.0.1:8765/mcp
        handle.shutdown()

    Args:
        port: TCP port to listen on.  Use ``0`` for a random available port.
        server_name: Name reported in MCP ``initialize`` response.
        server_version: Version reported in MCP ``initialize`` response.
        ws_host: Hostname of the Photoshop UXP WebSocket server.
        ws_port: Port of the Photoshop UXP WebSocket server.
    """

    def __init__(
        self,
        port: int = 8765,
        server_name: str = "photoshop-mcp",
        server_version: str = "0.1.0",
        ws_host: str = "localhost",
        ws_port: int = 9001,
    ) -> None:
        from dcc_mcp_core import McpHttpConfig, create_skill_manager  # noqa: PLC0415

        self._ws_host = ws_host
        self._ws_port = ws_port

        self._config = McpHttpConfig(
            port=port,
            server_name=server_name,
            server_version=server_version,
        )
        # create_skill_manager pre-wires ActionRegistry + ActionDispatcher + SkillCatalog
        self._server = create_skill_manager("photoshop", self._config)
        self._handle = None

    # ── bridge lifecycle ───────────────────────────────────────────────────

    def _connect_bridge(self) -> None:
        """Connect the WebSocket bridge (best-effort; warns on failure)."""
        from dcc_mcp_photoshop import api  # noqa: PLC0415
        from dcc_mcp_photoshop.bridge import PhotoshopBridge  # noqa: PLC0415

        bridge = PhotoshopBridge(host=self._ws_host, port=self._ws_port)
        try:
            bridge.connect()
            api._bridge = bridge
            logger.info(
                "PhotoshopBridge connected to ws://%s:%d",
                self._ws_host,
                self._ws_port,
            )
        except Exception as exc:
            logger.warning(
                "PhotoshopBridge could not connect to ws://%s:%d: %s — "
                "skill calls will fail until the Photoshop UXP plugin is running",
                self._ws_host,
                self._ws_port,
                exc,
            )

    def _disconnect_bridge(self) -> None:
        """Disconnect the bridge and clear the module-level singleton."""
        from dcc_mcp_photoshop import api  # noqa: PLC0415

        bridge = api._bridge
        if bridge is not None:
            try:
                bridge.disconnect()
            except Exception as exc:
                logger.debug("PhotoshopBridge disconnect error: %s", exc)
            api._bridge = None
            logger.info("PhotoshopBridge disconnected")

    # ── action / skill registration ────────────────────────────────────────

    @property
    def registry(self):
        """The underlying ``ActionRegistry`` (internal; prefer ``list_skills``).

        .. deprecated::
            With ``create_skill_manager`` (v0.12.12+), the registry is managed
            internally.  Use ``self._server.list_skills()`` or the HTTP
            ``tools/list`` endpoint to inspect registered tools.
        """
        return getattr(self._server, "_registry", None)

    def register_builtin_actions(
        self, extra_skill_paths: Optional[List[str]] = None
    ) -> "PhotoshopMcpServer":
        """Discover and load all built-in Photoshop skills into the server.

        Uses the dcc-mcp-core SkillCatalog API (v0.12.12+):

        1. ``server.discover(extra_paths, dcc_name="photoshop")`` — scans all
           paths for ``SKILL.md`` files and caches skill metadata.
        2. ``server.load_skill(name)`` — registers each script as an MCP action
           with the canonical naming convention::

               {skill_name.replace("-", "_")}__{script_stem}
               # e.g. photoshop_document__get_document_info

        Skills are discovered from (highest → lowest priority):

        - ``extra_skill_paths`` supplied by the caller
        - Built-in ``skills/`` directory shipped with this package
        - ``DCC_MCP_PHOTOSHOP_SKILL_PATHS`` environment variable
        - ``DCC_MCP_SKILL_PATHS`` environment variable
        - Platform default skills directory

        Args:
            extra_skill_paths: Additional directories to scan for SKILL.md files.

        Returns:
            ``self`` for fluent chaining::

                server = PhotoshopMcpServer().register_builtin_actions()
        """
        search_paths = _collect_skill_search_paths(extra_skill_paths)

        count = self._server.discover(extra_paths=search_paths, dcc_name="photoshop")
        logger.debug("SkillCatalog discovered %d skill(s)", count)

        loaded = 0
        failed = 0
        for summary in self._server.list_skills():
            skill_name = summary.name if hasattr(summary, "name") else summary["name"]
            try:
                self._server.load_skill(skill_name)
                loaded += 1
            except Exception as exc:
                logger.warning("Failed to load skill %r: %s", skill_name, exc)
                failed += 1

        logger.info(
            "Skills loaded: %d loaded, %d failed (from %d discovered)",
            loaded,
            failed,
            count,
        )
        return self

    # ── skill discovery helpers ────────────────────────────────────────────

    def find_skills(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dcc: Optional[str] = None,
    ) -> List[Any]:
        """Search the SkillCatalog using ``SkillCatalog.find_skills`` (v0.12.12+).

        Args:
            query: Free-text search term.
            tags: List of tags that the skill must have all of.
            dcc: If given, restrict to skills targeting this DCC.

        Returns:
            List of ``SkillSummary`` objects (or dicts).
        """
        try:
            return list(self._server.find_skills(query=query, tags=tags, dcc=dcc))
        except Exception as exc:
            logger.debug("find_skills failed: %s", exc)
            return []

    def is_skill_loaded(self, name: str) -> bool:
        """Check whether a skill has been loaded into the SkillCatalog.

        Args:
            name: Skill name as discovered (e.g. ``"photoshop-document"``).

        Returns:
            ``True`` if the skill is currently loaded.
        """
        try:
            return bool(self._server.is_loaded(name))
        except Exception as exc:
            logger.debug("is_loaded(%r) failed: %s", name, exc)
            return False

    def get_skill_info(self, name: str) -> Any:
        """Return full metadata for a skill from the SkillCatalog.

        Args:
            name: Skill name (e.g. ``"photoshop-document"``).

        Returns:
            ``SkillMetadata`` instance (or dict), or ``None`` if not found.
        """
        try:
            return self._server.get_skill_info(name)
        except Exception as exc:
            logger.debug("get_skill_info(%r) failed: %s", name, exc)
            return None

    # ── capabilities ──────────────────────────────────────────────────────

    def get_capabilities(self) -> Any:
        """Return the Photoshop DCC capabilities as a ``DccCapabilities`` instance.

        Returns:
            ``dcc_mcp_core.DccCapabilities`` instance with Photoshop-specific flags.

        Example::

            caps = server.get_capabilities()
            print(caps.has_embedded_python)   # False
            print(caps.to_dict())
        """
        from dcc_mcp_photoshop.capabilities import photoshop_capabilities  # noqa: PLC0415

        return photoshop_capabilities()

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> Any:
        """Start the MCP HTTP server and connect the WebSocket bridge.

        The bridge connection is best-effort: if Photoshop / the UXP plugin
        is not running, a warning is logged but the MCP server still starts.
        Skill calls will return ``ps_error`` results until the bridge connects.

        Returns:
            ``McpServerHandle`` with ``.mcp_url()``, ``.port``, ``.shutdown()``.
        """
        if self._handle is not None:
            logger.warning(
                "PhotoshopMcpServer already running on port %d", self._handle.port
            )
            return self._handle

        self._connect_bridge()
        self._handle = self._server.start()
        logger.info("Photoshop MCP server started at %s", self._handle.mcp_url())
        return self._handle

    def stop(self) -> None:
        """Gracefully stop the MCP HTTP server and disconnect the bridge."""
        if self._handle is not None:
            self._handle.shutdown()
            self._handle = None
            logger.info("Photoshop MCP server stopped")
        self._disconnect_bridge()

    @property
    def is_running(self) -> bool:
        """Whether the server is currently running."""
        return self._handle is not None

    @property
    def mcp_url(self) -> Optional[str]:
        """The MCP endpoint URL, or ``None`` if not running."""
        return self._handle.mcp_url() if self._handle else None


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_server_instance: Optional[PhotoshopMcpServer] = None
_lock = threading.Lock()


def start_server(
    port: int = 8765,
    server_name: str = "photoshop-mcp",
    ws_host: str = "localhost",
    ws_port: int = 9001,
    register_builtins: bool = True,
    extra_skill_paths: Optional[List[str]] = None,
) -> Any:
    """Start (or return the already-running) Photoshop MCP server.

    Creates a module-level singleton :class:`PhotoshopMcpServer`, optionally
    discovers and loads all built-in Photoshop skills, and starts the HTTP
    server.  Also connects the WebSocket bridge to the Photoshop UXP plugin
    (best-effort).

    Args:
        port: TCP port.  Use ``0`` for a random available port.
        server_name: Name shown in MCP ``initialize`` response.
        ws_host: Hostname of the Photoshop UXP WebSocket server.
        ws_port: Port of the Photoshop UXP WebSocket server.
        register_builtins: If ``True``, discovers and loads all built-in skills.
        extra_skill_paths: Additional directories to scan for ``SKILL.md`` files.

    Returns:
        ``McpServerHandle`` with ``.mcp_url()``, ``.port``, ``.shutdown()``.

    Example::

        import dcc_mcp_photoshop
        handle = dcc_mcp_photoshop.start_server(port=8765)
        print(handle.mcp_url())  # http://127.0.0.1:8765/mcp

        # With custom skill paths:
        handle = dcc_mcp_photoshop.start_server(extra_skill_paths=["/studio/ps-skills"])
    """
    global _server_instance
    with _lock:
        if _server_instance is None or not _server_instance.is_running:
            _server_instance = PhotoshopMcpServer(
                port=port,
                server_name=server_name,
                ws_host=ws_host,
                ws_port=ws_port,
            )
            if register_builtins:
                _server_instance.register_builtin_actions(
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
    """Return the current module-level singleton server instance, or ``None``.

    Example::

        server = get_server()
        if server and server.is_running:
            print(server.mcp_url)
    """
    return _server_instance
