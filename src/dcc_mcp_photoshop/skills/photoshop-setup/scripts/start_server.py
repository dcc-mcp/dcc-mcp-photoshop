"""Start the dcc-mcp-photoshop MCP server in embedded mode."""

from __future__ import annotations

import logging
import os
import socket
import time

from dcc_mcp_core.skill import skill_entry

logger = logging.getLogger(__name__)


def _port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex((host, port))
        return result == 0


@skill_entry
def start_server(
    mcp_port: int = 8765,
    ws_port: int = 9001,
    rpc_port: int = 9100,
    timeout: int = 30,
    **kwargs,
) -> dict:
    """Start the dcc-mcp-photoshop server in embedded mode for testing.

    Args:
        mcp_port: MCP HTTP server port.
        ws_port: WebSocket port for UXP plugin connection.
        rpc_port: RPC port for bridge access.
        timeout: Seconds to wait for UXP plugin connection.

    Returns:
        dict: Server start result with status and connection info.
    """
    # Check if ports are already in use
    ports_in_use = {}
    for name, port in [("MCP", mcp_port), ("WebSocket", ws_port), ("RPC", rpc_port)]:
        ports_in_use[name] = _port_in_use("127.0.0.1", port)

    if ports_in_use["MCP"] and not ports_in_use["WebSocket"]:
        return {
            "success": False,
            "summary": "MCP port already in use but WebSocket is free — dcc-mcp-server may already be running",
            "details": {
                "ports": {
                    "mcp_port": mcp_port,
                    "ws_port": ws_port,
                    "rpc_port": rpc_port,
                },
                "ports_in_use": ports_in_use,
            },
            "prompt": (
                "If dcc-mcp-server is already running externally, use "
                "dcc-mcp-photoshop (bridge-only mode) instead, or stop "
                "the existing server first."
            ),
        }

    if ports_in_use["WebSocket"]:
        return {
            "success": True,
            "summary": "Server already appears to be running on these ports",
            "details": {
                "ports": {
                    "mcp_port": mcp_port,
                    "ws_port": ws_port,
                    "rpc_port": rpc_port,
                },
                "ports_in_use": ports_in_use,
            },
            "prompt": "Run verify_connection to confirm the bridge is working.",
        }

    # Try to start the embedded server
    try:
        import dcc_mcp_photoshop  # noqa: PLC0415

        handle = dcc_mcp_photoshop.start_server(
            port=mcp_port,
            ws_port=ws_port,
            rpc_port=rpc_port,
            register_builtins=True,
            extra_skill_paths=os.environ.get("DCC_MCP_PHOTOSHOP_SKILL_PATHS", "").split(os.pathsep) or None,
        )

        mcp_url = handle.mcp_url() if hasattr(handle, "mcp_url") else f"http://127.0.0.1:{mcp_port}/mcp"

        # Wait for UXP plugin connection
        connected = False
        for _ in range(timeout):
            if _port_in_use("127.0.0.1", ws_port):
                connected = True
                break
            try:
                from dcc_mcp_photoshop.api import is_photoshop_available  # noqa: PLC0415
                if is_photoshop_available():
                    connected = True
                    break
            except Exception:
                pass
            time.sleep(1)

        return {
            "success": True,
            "summary": f"MCP server started at {mcp_url}",
            "details": {
                "mcp_url": mcp_url,
                "ports": {
                    "mcp_port": mcp_port,
                    "ws_port": ws_port,
                    "rpc_port": rpc_port,
                },
                "uxp_plugin_connected": connected,
                "wait_seconds": timeout,
            },
            "prompt": (
                f"Server is running. Connect your MCP client to {mcp_url}. "
                "Run verify_connection for a full check."
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "summary": f"Failed to start server: {exc}",
            "details": {
                "error": str(exc),
                "ports": {
                    "mcp_port": mcp_port,
                    "ws_port": ws_port,
                    "rpc_port": rpc_port,
                },
            },
            "prompt": (
                "Check the installation with check_environment, "
                "ensure dcc-mcp-core is installed, and retry."
            ),
        }


def main(**kwargs) -> dict:
    return start_server(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
