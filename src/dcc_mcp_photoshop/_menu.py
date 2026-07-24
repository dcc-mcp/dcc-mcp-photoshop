"""Unified menu actions for dcc-mcp-photoshop.

Provides Copy Instance ID, Server Info, and About DCC MCP actions
aligning with PIP-2799 (Maya) and PIP-2796 (Houdini) implementations.

Unlike Maya/Houdini where the menu is registered inside the DCC,
Photoshop communicates through the adobepy broker.  These actions
are callable from the UXP plugin (via the bridge), a standalone
Python panel, or MCP diagnostic tools.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from dcc_mcp_photoshop.__version__ import __version__

# ── instance ID resolution ──────────────────────────────────────────────


def resolve_instance_id() -> Optional[str]:
    """Return the Photoshop MCP instance ID for the active server, if available.

    Robust to every degraded state — missing server, server not yet
    started, Python path issues.  Returns ``None`` instead of a
    cosmetic sentinel like ``"unknown"``.
    """
    try:
        from dcc_mcp_photoshop import get_server  # noqa: PLC0415

        server = get_server()
        if server is None:
            return None

        # Primary: server.instance_id (set by DccServerBase during init)
        instance_id = getattr(server, "instance_id", None)
        if isinstance(instance_id, str) and instance_id.strip():
            return instance_id.strip()

        # Fallback: check _config.instance_id
        cfg = getattr(server, "_config", None)
        if cfg is not None:
            instance_id = getattr(cfg, "instance_id", None)
            if isinstance(instance_id, str) and instance_id.strip():
                return instance_id.strip()
    except Exception:
        pass
    return None


# ── clipboard ───────────────────────────────────────────────────────────


def set_clipboard_text(text: str) -> None:
    """Set the system clipboard text, trying PySide2 then PySide6.

    Raises:
        RuntimeError: If no PySide binding is available or no
            QApplication instance exists.
    """
    for binding in ("PySide2", "PySide6"):
        try:
            mod = __import__(binding)
            app = mod.QtWidgets.QApplication.instance()
            if app is not None:
                app.clipboard().setText(text)
                return
        except Exception:
            continue
    raise RuntimeError("Unable to access system clipboard (no PySide binding available)")


# ── copy instance ID ────────────────────────────────────────────────────


def copy_instance_id() -> str:
    """Copy the DCC MCP instance UUID to the system clipboard.

    Returns:
        The instance ID that was copied.

    Raises:
        RuntimeError: If the instance ID is not available (server not
            running) or clipboard access fails.
    """
    instance_id = resolve_instance_id()
    if not instance_id:
        raise RuntimeError("Instance ID not available. Is the server running?")
    set_clipboard_text(instance_id)
    return instance_id


# ── server info ─────────────────────────────────────────────────────────


def format_server_info() -> str:
    """Return a formatted server information string.

    Follows the same structure as the Maya ``_show_server_info()`` dialog
    but returns the message string instead of showing a dialog, so it can
    be displayed by the UXP plugin, a Python panel, or printed to stdout.
    """
    instance_id = resolve_instance_id()
    instance_url = ""

    try:
        from dcc_mcp_photoshop import get_server  # noqa: PLC0415

        server = get_server()
        if server is not None:
            instance_url = getattr(server, "mcp_url", "") or ""
    except Exception:
        pass

    gateway_port_str = os.environ.get("DCC_MCP_GATEWAY_PORT", "0")
    try:
        gp = int(gateway_port_str)
    except ValueError:
        gp = 0
    gateway_display = "disabled" if gp <= 0 else str(gp)

    core_version = "unknown"
    try:
        from dcc_mcp_core.server_base import _package_version  # noqa: PLC0415

        core_version = _package_version() or "unknown"
    except Exception:
        pass

    return (
        f"Instance UUID: {instance_id or 'N/A'}\n"
        f"DCC: Photoshop (via adobepy)\n"
        f"PID: {os.getpid()}\n"
        f"MCP URL: {instance_url or 'N/A'}\n"
        f"Gateway Port: {gateway_display}\n"
        f"Core Version: {core_version}\n"
        f"Adapter Version: {__version__}\n"
        f"Python: {sys.version.split()[0]}"
    )


# ── about ───────────────────────────────────────────────────────────────


def format_about() -> str:
    """Return a formatted about string.

    Follows the same structure as the Maya ``_show_about()`` dialog.
    """
    return (
        f"dcc-mcp-photoshop v{__version__}\n"
        f"Python {sys.version.split()[0]}\n\n"
        "DCC MCP — AI-driven DCC automation.\n"
        "https://github.com/dcc-mcp/dcc-mcp-photoshop"
    )
