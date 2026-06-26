"""Photoshop DCC capabilities declaration using dcc-mcp-core's DccCapabilities.

This module provides a single factory function :func:`photoshop_capabilities`
that returns a ``DccCapabilities`` instance declaring what this Photoshop
integration supports.

Key differences from embedded-Python DCCs (Maya, Blender):

- ``has_embedded_python = False`` — Photoshop does not ship a Python interpreter;
  all automation runs via the UXP JavaScript API.
- ``bridge_kind = "adobepy_broker"`` — Communication uses the adobepy Rust broker
  (port 47391) which proxies between Python SDK and the UXP bridge.
- ``bridge_endpoint = "http://127.0.0.1:47391"`` — adobepy broker HTTP endpoint.

Supported capability flags for Photoshop:

- ``scene_manager``   — open/close/save documents (``ps.openDocument``, etc.)
- ``selection``       — pixel / layer selections (``ps.makeSelection``, etc.)
- ``render_capture``  — export/save-as via Photoshop actions
- ``snapshot``        — ``ps.saveDocumentAs`` to PNG/JPEG for quick previews
- ``file_operations`` — import/export in multiple formats (PNG, JPEG, PSD, TIFF)
- ``has_embedded_python`` — ``False``; Python runs externally via bridge
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["photoshop_capabilities", "PHOTOSHOP_CAPABILITIES_DICT"]


def photoshop_capabilities():
    """Return a ``DccCapabilities`` instance for the Photoshop integration.

    All flags reflect capabilities available in Photoshop 2022+ (UXP support).

    Returns:
        ``dcc_mcp_core.DccCapabilities`` instance.

    Example::

        caps = photoshop_capabilities()
        print(caps.has_embedded_python)   # False
        print(caps.to_dict())             # {...}
    """
    from dcc_mcp_core import DccCapabilities  # noqa: PLC0415

    return DccCapabilities(
        scene_manager=True,
        selection=True,
        render_capture=True,
        snapshot=True,
        file_operations=True,
        has_embedded_python=False,
        # Bridge mode: Python communicates via adobepy Rust broker to UXP bridge
        bridge_kind="adobepy_broker",
        # adobepy broker HTTP endpoint (Python SDK connects here)
        bridge_endpoint="http://127.0.0.1:47391",
    )


# Pre-computed plain dict — available without importing dcc_mcp_core at import
# time.  Useful for fast serialisation or when dcc_mcp_core is unavailable.
PHOTOSHOP_CAPABILITIES_DICT = {
    "scene_manager": True,
    "selection": True,
    "render_capture": True,
    "snapshot": True,
    "file_operations": True,
    "has_embedded_python": False,
    "bridge_kind": "adobepy_broker",
    "bridge_endpoint": "http://127.0.0.1:47391",
}
