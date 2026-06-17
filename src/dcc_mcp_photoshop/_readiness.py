"""Runtime readiness wiring for :class:`PhotoshopMcpServer`.

Photoshop's embedded MCP HTTP server publishes itself to the gateway
before the adobepy broker connection is verified.  During that window
``list_dcc_instances`` may report ``status: "available"`` even though
skill calls will fail because the broker/UXP bridge is not ready.

This module delegates to core :class:`dcc_mcp_core.readiness.AdapterReadinessBinder`
(0.17.32+) for probe lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from dcc_mcp_core.readiness import AdapterReadinessBinder

from dcc_mcp_photoshop._env import resolve_readiness_timeout_secs

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ReadinessBinder — wraps a core AdapterReadinessBinder
# ---------------------------------------------------------------------------


class ReadinessBinder:
    """Drive readiness using core :class:`AdapterReadinessBinder`.

    The Photoshop server has two readiness dimensions:
    - ``process`` — the HTTP server process is alive
    - ``dispatcher`` — the inline executor is ready (always true for Photoshop)

    Unlike Maya, Photoshop does not have a separate main-thread dispatcher,
    so the ``dcc`` bit is flipped optimistically when the broker check passes.

    Usage (called once from ``PhotoshopMcpServer.__init__``)::

        binder = ReadinessBinder()
        binder.bind(server)

    Parameters
    ----------
    timeout_secs:
        Advisory timeout (seconds) for how long a cold Photoshop can
        stall before callers should consider readiness permanently red.
        Unset → no timeout; the gateway / orchestrator decides.
    """

    def __init__(self, *, timeout_secs: Optional[int] = None) -> None:
        self.timeout_secs: Optional[int] = resolve_readiness_timeout_secs(timeout_secs)
        # Create the core ReadinessProbe eagerly so tests can inspect it
        from dcc_mcp_core import ReadinessProbe  # noqa: PLC0415

        self.probe: ReadinessProbe = ReadinessProbe()
        self._adapter_binder: Optional[AdapterReadinessBinder] = None
        self.bound_server: Any = None  # type: ignore[explicit-any]

    # ── Public API (delegates to core ReadinessProbe via AdapterReadinessBinder) ─

    @property
    def published_to_server(self) -> bool:
        """Whether the probe was published to the inner Rust server."""
        return self._adapter_binder.published if self._adapter_binder else False

    def report(self) -> dict:
        """Return the current readiness snapshot as a dict.

        Keys: ``process`` / ``dispatcher`` / ``dcc``.
        """
        return self.probe.report()

    def is_ready(self) -> bool:
        """Return ``True`` when all bits are green."""
        return self.probe.is_ready()

    def bind(self, server: Any) -> bool:  # type: ignore[explicit-any]
        """Wire the probe into *server*.

        Steps:

        1. Create a core ``AdapterReadinessBinder`` that publishes
           the shared probe to the inner Rust ``McpHttpServer`` via
           ``set_readiness_probe``.
        2. Mark all bits green — Photoshop uses inline execution, so
           there is no separate dispatcher thread to wait on.
        """
        if self.bound_server is server:
            return True
        self.bound_server = server

        # Step 1 — create core AdapterReadinessBinder with the shared probe
        self._adapter_binder = AdapterReadinessBinder(server, probe=self.probe, publish=True)

        # Step 2 — Photoshop uses inline execution: no separate main thread
        self._adapter_binder.mark_dispatcher_ready(
            True,
            host_execution_bridge_ready=True,
            main_thread_executor_ready=True,
        )

        # Mark dcc ready — the inline executor handles everything
        self._adapter_binder.mark_inline_ready()

        logger.info("[photoshop] readiness: all-green (inline executor)")
        return True

    def mark_dcc_ready(self, value: bool = True) -> None:
        """Flip the ``dcc`` bit.  Typically called when broker connectivity is confirmed."""
        self.probe.set_dcc_ready(value)
        if value:
            logger.info("[photoshop] readiness: dcc-ready — broker is reachable")


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def install_readiness(
    server: Any,  # type: ignore[explicit-any]
    *,
    timeout_secs: Optional[int] = None,
) -> ReadinessBinder:
    """One-shot helper used by :class:`PhotoshopMcpServer.__init__`."""
    binder = ReadinessBinder(timeout_secs=timeout_secs)
    binder.bind(server)
    return binder
