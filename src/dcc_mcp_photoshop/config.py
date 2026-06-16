"""Configuration for dcc-mcp-photoshop adapter.

All values can be overridden via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass
class PhotoshopMcpConfig:
    """Photoshop MCP adapter configuration.

    All values can be overridden via environment variables.
    """

    # --- Broker connection (adobepy) ---
    broker_url: str = field(
        default_factory=lambda: os.getenv(
            "ADOBEPY_BROKER_URL", "http://127.0.0.1:47391"
        )
    )
    broker_token: str = field(
        default_factory=lambda: os.getenv("ADOBEPY_TOKEN", "dev-token")
    )
    broker_target: str = field(
        default_factory=lambda: os.getenv("ADOBEPY_TARGET", "default")
    )

    # --- MCP server ---
    mcp_port: int = field(
        default_factory=lambda: int(
            os.getenv("DCC_MCP_PHOTOSHOP_PORT", "8765")
        )
    )
    gateway_port: Optional[int] = field(
        default_factory=lambda: _parse_optional_int(
            os.getenv("DCC_MCP_GATEWAY_PORT")
        )
    )
    server_name: str = field(
        default_factory=lambda: os.getenv(
            "DCC_MCP_PHOTOSHOP_SERVER_NAME", "photoshop-mcp"
        )
    )

    # --- Logging ---
    log_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "DCC_MCP_PHOTOSHOP_LOG_DIR",
                str(Path.home() / ".dcc-mcp" / "logs"),
            )
        )
    )
    log_level: str = field(
        default_factory=lambda: os.getenv(
            "DCC_MCP_PHOTOSHOP_LOG_LEVEL", "INFO"
        )
    )

    # --- Timeout ---
    timeout: float = field(
        default_factory=lambda: float(
            os.getenv("DCC_MCP_PHOTOSHOP_TIMEOUT", "30.0")
        )
    )

    @classmethod
    def from_env(cls) -> PhotoshopMcpConfig:
        """Create configuration from environment variables.

        Equivalent to ``PhotoshopMcpConfig()`` since all fields read
        from environment by default.  Provided as an explicit factory
        for readability.
        """
        return cls()
