"""Route legacy Photoshop bridge setup calls to the canonical lifecycle."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from dcc_mcp_core.skill import skill_entry


def _default_bridge_dir() -> Path:
    if platform.system() == "Windows":
        root = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    else:
        root = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(root) / "adobepy" / "bridges" / "photoshop"


@skill_entry
def setup_uxp_plugin(
    method: str = "auto",
    bridge_dir: str = "",
    adobepy_executable: str = "",
    **kwargs,
) -> dict:
    """Return the canonical install command without staging a second bridge.

    Adobe owns developer-plugin registration and loading. The adapter lifecycle
    owns staging, receipts, rollback, and readiness verification.
    """
    destination = Path(bridge_dir).expanduser() if bridge_dir else _default_bridge_dir()
    command = ["dcc-mcp-photoshop", "install", "--json", "--yes"]
    return {
        "success": True,
        "summary": "Use the canonical Photoshop install lifecycle",
        "details": {
            "state": "canonical_redirect",
            "legacy_method": method,
            "requested_bridge_dir": str(destination),
            "requested_adobepy_executable": bool(adobepy_executable),
        },
        "next_steps": [
            {
                "id": "canonical-install",
                "description": "Run the canonical Photoshop install lifecycle",
                "command": command,
                "why": "The canonical lifecycle owns staging, receipts, rollback, and verify-to-usable",
            }
        ],
        "prompt": "Run: " + " ".join(command),
    }


def main(**kwargs) -> dict:
    return setup_uxp_plugin(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
