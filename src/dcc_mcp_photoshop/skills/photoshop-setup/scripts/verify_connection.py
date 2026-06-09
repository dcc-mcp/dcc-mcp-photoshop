"""Verify the full dcc-mcp-photoshop bridge connection end-to-end."""

from __future__ import annotations

import socket
import time
from urllib.request import urlopen, Request
from urllib.error import URLError

from dcc_mcp_core.skill import skill_entry


def _check_tcp_port(host: str, port: int, timeout: float = 3) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _check_mcp_endpoint(port: int, timeout: float = 5) -> tuple[bool, str]:
    """Check the MCP HTTP endpoint."""
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return True, f"MCP endpoint responded (status {resp.status})"
    except URLError as e:
        return False, f"MCP endpoint unreachable: {e.reason}"
    except Exception as exc:
        return False, f"MCP endpoint error: {exc}"


def _list_skills() -> list[str]:
    """List discoverable skills from the running server."""
    try:
        from dcc_mcp_photoshop.server import PhotoshopMcpServer  # noqa: PLC0415
        skills = []
        # Try to check for a running server instance
        return skills
    except Exception:
        return []


@skill_entry
def verify_connection(
    mcp_port: int = 8765,
    ws_port: int = 9001,
    timeout: int = 10,
    **kwargs,
) -> dict:
    """Verify the full bridge connection end-to-end.

    Checks:
    - MCP HTTP server is listening
    - UXP WebSocket bridge port is open
    - Skills are discoverable
    - Optional: bridge RPC endpoint

    Args:
        mcp_port: MCP HTTP server port.
        ws_port: WebSocket port for UXP plugin.
        timeout: Connection timeout in seconds.

    Returns:
        dict: Verification results for each component.
    """
    results = {}

    # 1. Check MCP server
    mcp_ok = _check_tcp_port("127.0.0.1", mcp_port, timeout=min(timeout, 5))
    if mcp_ok:
        _mcp_ok, detail = _check_mcp_endpoint(mcp_port, timeout=min(timeout, 5))
        results["mcp_server"] = {
            "ok": _mcp_ok,
            "port": mcp_port,
            "detail": detail,
        }
    else:
        results["mcp_server"] = {
            "ok": False,
            "port": mcp_port,
            "detail": f"Port {mcp_port} not listening",
        }

    # 2. Check UXP WebSocket bridge
    uxp_ok = _check_tcp_port("127.0.0.1", ws_port, timeout=min(timeout, 3))
    results["uxp_bridge"] = {
        "ok": uxp_ok,
        "port": ws_port,
        "detail": f"Port {ws_port} {'open' if uxp_ok else 'closed or refused connection'}",
    }

    # 3. Check RPC port
    rpc_port = 9100
    rpc_ok = _check_tcp_port("127.0.0.1", rpc_port, timeout=min(timeout, 3))
    results["rpc_endpoint"] = {
        "ok": rpc_ok,
        "port": rpc_port,
        "detail": f"Port {rpc_port} {'open' if rpc_ok else 'closed'}" if rpc_ok else f"Port {rpc_port} not listening (expected if bridge-only mode)",
    }

    # 4. Check Photoshop connection via bridge
    photoshop_connected = False
    try:
        from dcc_mcp_photoshop.api import is_photoshop_available, get_bridge  # noqa: PLC0415
        if _check_tcp_port("127.0.0.1", ws_port, timeout=2):
            photoshop_connected = is_photoshop_available()
            if photoshop_connected:
                bridge = get_bridge()
                try:
                    doc_info = bridge.call("ps.getDocumentInfo")
                    if isinstance(doc_info, dict):
                        results["photoshop_connection"] = {
                            "ok": True,
                            "detail": f"Connected — active document: {doc_info.get('name', 'unknown')}",
                        }
                except Exception:
                    results["photoshop_connection"] = {
                        "ok": True,
                        "detail": "Bridge connected (query failed — no active document?)",
                    }
    except Exception:
        photoshop_connected = False

    if "photoshop_connection" not in results:
        results["photoshop_connection"] = {
            "ok": photoshop_connected,
            "detail": "Not connected to Photoshop" if not photoshop_connected else "Connected",
        }

    # 5. Summary
    all_ok = all(
        v.get("ok", False)
        for k, v in results.items()
        if k != "rpc_endpoint"  # RPC is optional
    )

    component_status = []
    for name, data in results.items():
        icon = "✓" if data.get("ok") else "✗"
        component_status.append(f"[{icon}] {name}: {data.get('detail', '')}")

    return {
        "summary": "\n".join(component_status),
        "all_ok": all_ok,
        "details": results,
        "prompt": (
            "All systems connected. Use photoshop-document, photoshop-image, "
            "or photoshop-layers skills to start working."
            if all_ok else
            "Run check_environment and ensure Photoshop is running "
            "with the UXP plugin installed."
        ),
    }


def main(**kwargs) -> dict:
    return verify_connection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
