"""Capability manifest builder for Photoshop.

Builds a structured capability manifest for gateway aggregation,
similar to the Maya :class:`MayaCapabilityManifestBuilder`.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PhotoshopCapabilityManifestBuilder:
    """Build a capability manifest for gateway discovery.

    The manifest describes what this Photoshop adapter can do:
    - DCC type and version
    - Available skill packages and their tools
    - Connection method (adobepy broker)
    - Supported file formats
    - Current session state
    """

    def __init__(self, server: Any) -> None:  # type: ignore[explicit-any]
        self._server = server

    def build(self) -> dict[str, Any]:
        """Build the capability manifest.

        Returns a dict with keys:
        - ``dcc_type``: ``"photoshop"``
        - ``dcc_version``: Photoshop version string (if known)
        - ``adapter_version``: package version
        - ``connection``: connection method info
        - ``skills``: list of available skill packages
        - ``formats``: supported file formats
        """
        manifest: dict[str, Any] = {
            "dcc_type": "photoshop",
            "dcc_version": self._detect_version(),
            "adapter_version": self._get_adapter_version(),
            "connection": {
                "method": "adobepy_broker",
                "protocol": "JSON-RPC 2.0",
                "default_port": 47391,
            },
            "formats": [
                "psd",
                "psb",
                "tiff",
                "jpeg",
                "png",
                "gif",
                "bmp",
                "pdf",
                "raw",
            ],
            "skills": self._list_skills(),
            "session": self._session_info(),
        }
        return manifest

    def _detect_version(self) -> str:
        """Best-effort Photoshop version detection."""
        try:
            if hasattr(self._server, "_config"):
                # Could query broker for real version here
                return "25.0+"  # Photoshop 2024+
        except Exception:
            pass
        return "unknown"

    def _get_adapter_version(self) -> str:
        """Get the adapter package version."""
        try:
            from dcc_mcp_photoshop import __version__  # noqa: PLC0415

            return __version__
        except Exception:
            return "unknown"

    def _list_skills(self) -> list[dict[str, Any]]:
        """List available skill packages with their tool counts."""
        try:
            if hasattr(self._server, "_server"):
                catalog = self._server._server.skill_catalog  # noqa: SLF001
                if catalog is not None:
                    return [
                        {
                            "name": skill.name,
                            "version": skill.version,
                            "dcc": skill.dcc,
                            "tags": skill.tags,
                        }
                        for skill in catalog.list_all()
                    ]
        except Exception:
            pass
        return []

    def _session_info(self) -> dict[str, Any]:
        """Collect session state info."""
        return {
            "active": self._server.is_running if hasattr(self._server, "is_running") else False,
            "broker_ready": self._is_broker_ready(),
        }

    def _is_broker_ready(self) -> bool:
        """Check if the adobepy broker is reachable."""
        try:
            if hasattr(self._server, "_startup_state"):
                state = self._server._startup_state  # noqa: SLF001
                return state.stage in ("broker_ready", "skills_discovering", "dispatch_ready")
        except Exception:
            pass
        return False
