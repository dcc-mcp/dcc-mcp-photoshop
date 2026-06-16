"""PhotoshopMcpServer — MCP server for Adobe Photoshop.

Uses the adobepy Rust broker to communicate with Photoshop via the UXP bridge.
Skill scripts call the ``adobe.photoshop.Photoshop()`` facade which connects
to the broker at ``ADOBEPY_BROKER_URL`` (default ``http://127.0.0.1:47391``).

Flow::

    MCP Client -> PhotoshopMcpServer (HTTP:8765)
        Skill scripts -> adobe.photoshop.Photoshop() -> BrokerClient -> adobepy broker (HTTP:47391)
            -> adobepy UXP bridge (WS:47391) -> Photoshop UXP API

Configuration::

    Environment variables:
      ADOBEPY_BROKER_URL  Broker HTTP endpoint (default: http://127.0.0.1:47391)
      ADOBEPY_TOKEN       Authentication token (default: dev-token)
      DCC_MCP_PHOTOSHOP_PORT  MCP HTTP server port (default: 8765)
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from dcc_mcp_core._server.options import DccServerOptions
from dcc_mcp_core.server_base import DccServerBase

from dcc_mcp_photoshop.config import PhotoshopMcpConfig

logger = logging.getLogger(__name__)

# Built-in skills directory shipped with this package
_BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"


# ---------------------------------------------------------------------------
# Startup state — tracks failure stage for diagnostics
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class StartupState:
    """Tracks the server startup lifecycle for diagnostics.

    The server transitions through:
      booting → broker_checking → broker_ready
      → skills_discovering → dispatch_ready

    On failure the state carries ``failure_stage`` and
    ``recommended_next_action`` so operators and the gateway can
    query what went wrong and what to do about it.
    """

    stage: str = "booting"
    """Current startup stage (booting / broker_checking / broker_ready /
    skills_discovering / dispatch_ready / failed)."""

    failure_stage: str = ""
    """If ``stage == "failed"``, which sub-stage failed."""

    recommended_next_action: str = ""
    """Human-readable description of how to resolve the failure."""

    def set_failed(self, failure_stage: str, action: str) -> None:
        """Transition to the ``failed`` state and record diagnostics."""
        self.stage = "failed"
        self.failure_stage = failure_stage
        self.recommended_next_action = action
        logger.error("Startup failed at stage=%s: %s", failure_stage, action)


# ---------------------------------------------------------------------------
# PhotoshopMcpServer — extends DccServerBase (4-seam controller, PIP-688)
# ---------------------------------------------------------------------------


class PhotoshopMcpServer(DccServerBase):
    """MCP server for Adobe Photoshop, extends :class:`DccServerBase`.

    Inherits the 4-seam controller architecture (PIP-688):
    :class:`SkillDiscoveryController`, :class:`ExecutionBridgeBinder`,
    :class:`LifecycleController`, :class:`ObservabilityFacade`.

    Skill scripts use ``adobe.photoshop.Photoshop()`` facade which connects
    to the adobepy Rust broker (port 47391 by default).

    Args:
        config: ``PhotoshopMcpConfig`` instance.  If ``None``, reads from env.
        port: TCP port for the MCP HTTP server (overrides config).
        server_name: Name reported in MCP ``initialize`` response.
        server_version: Version reported in MCP ``initialize`` response.
        gateway_port: Gateway competition port.  ``None`` reads env var, ``0`` disables.
    """

    def __init__(
        self,
        config: Optional[PhotoshopMcpConfig] = None,
        port: int | None = None,
        server_name: str = "photoshop-mcp",
        server_version: str = "0.2.0",
        gateway_port: int | None = None,
    ) -> None:
        self._config = config or PhotoshopMcpConfig.from_env()
        self._startup_state = StartupState()

        options = DccServerOptions.from_env(
            dcc_name="photoshop",
            builtin_skills_dir=_BUILTIN_SKILLS_DIR,
            port=port if port is not None else self._config.mcp_port,
            server_name=server_name,
            server_version=server_version,
            gateway_port=gateway_port if gateway_port is not None else self._config.gateway_port,
        )
        super().__init__(options=options)

    # ── broker health check ─────────────────────────────────────────────────

    def _check_broker(self) -> None:
        """Verify adobepy broker is reachable (best-effort; warns on failure)."""
        self._startup_state.stage = "broker_checking"
        try:
            from adobe.core.client import BrokerClient  # noqa: PLC0415

            client = BrokerClient(
                broker_url=self._config.broker_url,
                token=self._config.broker_token,
                timeout=self._config.timeout,
            )
            caps = client.capabilities()
            self._startup_state.stage = "broker_ready"
            logger.info(
                "adobepy broker available at %s (target=%s)",
                self._config.broker_url,
                caps.get("target", self._config.broker_target),
            )
        except Exception as exc:
            self._startup_state.set_failed(
                "broker_check",
                f"adobepy broker not reachable at {self._config.broker_url}: {exc}. "
                "Start the broker with 'adobepy broker' and ensure the UXP bridge is loaded.",
            )
            logger.warning(
                "adobepy broker not reachable at %s: %s — "
                "skill calls will fail until the broker and UXP bridge are running",
                self._config.broker_url,
                exc,
            )

    # ── action / skill registration ────────────────────────────────────────

    def discover_builtin_skills(self, extra_skill_paths: list[str] | None = None) -> PhotoshopMcpServer:
        """Discover all built-in Photoshop skills (lazy loading mode).

        This only scans for skills; it does NOT load them. Skills remain
        unloaded until explicitly requested via the ``load_skill`` meta-tool.

        Args:
            extra_skill_paths: Additional directories to scan for SKILL.md files.

        Returns:
            ``self`` for fluent chaining
        """
        paths = self.collect_skill_search_paths(extra_paths=extra_skill_paths)
        count = self._server.discover(extra_paths=paths)
        logger.info(
            "SkillCatalog discovered %d skill(s) — use load_skill to load them on-demand",
            count,
        )
        return self

    def register_builtin_actions(self, extra_skill_paths: list[str] | None = None) -> PhotoshopMcpServer:
        """DEPRECATED: Discover and eagerly load all built-in skills.

        .. deprecated:: 0.1.0
            Use :meth:`discover_builtin_skills` for lazy loading instead.
        """
        logger.warning(
            "register_builtin_actions is deprecated; use discover_builtin_skills() "
            "for lazy loading, or switch to dcc-mcp-server.exe in gateway mode"
        )
        super().register_builtin_actions(extra_skill_paths=extra_skill_paths)
        return self

    # ── skill discovery helpers ────────────────────────────────────────────

    def find_skills(self, query=None, tags=None, dcc=None):
        """Search for skills by query, tags, and DCC name."""
        return self.search_skills(query=query, tags=tags, dcc=dcc)

    # ── capabilities ──────────────────────────────────────────────────────

    def get_capabilities(self):
        """Return the :class:`DccCapabilities` for this Photoshop adapter."""
        from dcc_mcp_photoshop.capabilities import photoshop_capabilities  # noqa: PLC0415

        return photoshop_capabilities()

    # ── startup diagnostics ───────────────────────────────────────────────

    @property
    def startup_state(self) -> StartupState:
        """Return the current :class:`StartupState` for diagnostics."""
        return self._startup_state

    def diagnostics(self) -> dict:
        """Return a diagnostics snapshot for gateway / observability consumers.

        The returned dict includes:
        - ``dispatch_ready`` — whether tools can be dispatched
        - ``failure_stage`` — which stage failed (empty if no failure)
        - ``recommended_next_action`` — how to resolve a failure
        - ``broker_ready`` — whether adobepy broker is reachable
        - ``server_url`` — the MCP HTTP endpoint
        - ``gateway_status`` — gateway election status from ``DccServerBase``
        """
        d = {
            "dispatch_ready": self._startup_state.stage == "dispatch_ready",
            "startup_stage": self._startup_state.stage,
            "failure_stage": self._startup_state.failure_stage,
            "recommended_next_action": self._startup_state.recommended_next_action,
            "broker_ready": self._startup_state.stage == "broker_ready"
            or self._startup_state.stage in ("skills_discovering", "dispatch_ready"),
            "server_running": self.is_running,
            "server_url": self.mcp_url,
        }
        try:
            d["gateway_status"] = self.get_gateway_election_status()
        except Exception:
            d["gateway_status"] = {"error": "gateway election not available"}
        return d

    # ── lifecycle ──────────────────────────────────────────────────────────

    def _push_diagnostics(self) -> None:
        """Push current startup diagnostics to gateway metadata (best-effort)."""
        try:
            self.update_gateway_metadata(
                scene=self._startup_state.stage,
                version=self._startup_state.failure_stage,
            )
        except Exception:
            pass

    def start(self, *, install_atexit_hook: bool = True) -> Any:
        """Start the MCP HTTP server and verify broker connectivity."""
        self._push_diagnostics()
        self._check_broker()
        self._push_diagnostics()
        if self._startup_state.stage != "failed":
            self._startup_state.stage = "skills_discovering"
        self._push_diagnostics()
        try:
            handle = super().start(install_atexit_hook=install_atexit_hook)
            if self._startup_state.stage != "failed":
                self._startup_state.stage = "dispatch_ready"
            self._push_diagnostics()
            return handle
        except Exception as exc:
            self._startup_state.set_failed(
                "server_start",
                f"MCP HTTP server failed to start: {exc}. Check port availability and dcc-mcp-core installation.",
            )
            self._push_diagnostics()
            raise

    def stop(self) -> None:
        """Gracefully stop the MCP HTTP server."""
        super().stop()


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_server_instance: Optional[PhotoshopMcpServer] = None
_lock = threading.Lock()


def start_server(
    port: int = 8765,
    server_name: str = "photoshop-mcp",
    broker_url: str | None = None,
    gateway_port: int | None = None,
    register_builtins: bool = True,
    extra_skill_paths: list[str] | None = None,
) -> Any:
    """Start Photoshop MCP server in-process.

    Skill scripts use ``adobe.photoshop.Photoshop()`` facade which connects
    to the adobepy Rust broker.

    Args:
        port: TCP port for the MCP HTTP server.
        server_name: Name shown in MCP ``initialize`` response.
        broker_url: adobepy broker URL (default: ``ADOBEPY_BROKER_URL`` env or ``http://127.0.0.1:47391``).
        gateway_port: Gateway competition port. ``None`` reads env var, ``0`` disables.
        register_builtins: If ``True``, discovers skills (lazy loading).
        extra_skill_paths: Additional directories to scan for ``SKILL.md`` files.

    Returns:
        ``McpServerHandle`` with ``.mcp_url()``, ``.port``, ``.shutdown()``.
    """
    global _server_instance

    config = PhotoshopMcpConfig.from_env()
    if broker_url is not None:
        config.broker_url = broker_url

    with _lock:
        if _server_instance is None or not _server_instance.is_running:
            _server_instance = PhotoshopMcpServer(
                config=config,
                port=port,
                server_name=server_name,
                gateway_port=gateway_port,
            )
            if register_builtins:
                _server_instance.discover_builtin_skills(extra_skill_paths=extra_skill_paths)
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


def run_daemon(
    port: int = 8765,
    server_name: str = "photoshop-mcp",
    broker_url: str | None = None,
    gateway_port: int | None = None,
    register_builtins: bool = True,
    extra_skill_paths: list[str] | None = None,
) -> tuple[Any, StartupState]:
    """Start the Photoshop MCP server in daemon mode (no interactive loop).

    The server starts, registers with the gateway, and runs silently
    in the background.  Callers should use the returned ``handle`` to
    shut down via ``handle.shutdown()`` or ``stop_server()``.

    Args:
        port: TCP port for the MCP HTTP server.
        server_name: Name shown in MCP ``initialize`` response.
        broker_url: adobepy broker URL.
        gateway_port: Gateway competition port.
        register_builtins: If ``True``, discovers skills (lazy loading).
        extra_skill_paths: Additional directories to scan for SKILL.md files.

    Returns:
        Tuple of ``(handle, startup_state)`` where *handle* is the
        ``McpServerHandle`` and *startup_state* is the :class:`StartupState`
        that tracks the startup lifecycle.
    """
    global _server_instance

    config = PhotoshopMcpConfig.from_env()
    if broker_url is not None:
        config.broker_url = broker_url

    with _lock:
        if _server_instance is None or not _server_instance.is_running:
            _server_instance = PhotoshopMcpServer(
                config=config,
                port=port,
                server_name=server_name,
                gateway_port=gateway_port,
            )
            if register_builtins:
                _server_instance.discover_builtin_skills(extra_skill_paths=extra_skill_paths)
        handle = _server_instance.start()
        state = _server_instance.startup_state
    return handle, state
