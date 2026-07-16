"""Start the adobepy-backed Photoshop MCP server."""

from __future__ import annotations

from typing import Optional

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop.runtime_probe import probe_broker
from dcc_mcp_photoshop.server import get_server
from dcc_mcp_photoshop.server import start_server as start_adapter


@skill_entry
def start_server(
    mcp_port: Optional[int] = None,
    broker_url: str = "http://127.0.0.1:47391",
    gateway_port: int = 9765,
    **kwargs,
) -> dict:
    """Start the adapter only after its broker dependency is ready."""
    broker = probe_broker(broker_url, timeout=3)
    if not broker["ok"]:
        return {
            "success": False,
            "summary": "adobepy broker is not ready; Photoshop MCP server was not started",
            "details": {"broker": broker},
            "prompt": "Start adobepy broker, then retry start_server.",
        }

    try:
        handle = start_adapter(
            port=mcp_port,
            broker_url=broker_url,
            gateway_port=gateway_port,
            register_builtins=True,
        )
        diagnostics = get_server().diagnostics()
        ready = bool(diagnostics.get("dispatch_ready"))
        return {
            "success": ready,
            "summary": "Photoshop MCP server is dispatch ready"
            if ready
            else "Photoshop MCP server started but is not ready",
            "details": {"mcp_url": handle.mcp_url(), "broker": broker, "diagnostics": diagnostics},
            "prompt": "Run verify_connection to check the complete gateway-to-Photoshop chain.",
        }
    except Exception as exc:  # noqa: BLE001 - return actionable skill output
        return {
            "success": False,
            "summary": "Failed to start Photoshop MCP server",
            "details": {"broker": broker, "error": str(exc)},
            "prompt": "Check port ownership and dcc-mcp-core compatibility, then retry.",
        }


def main(**kwargs) -> dict:
    return start_server(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
