"""Verify the adobepy-backed Photoshop MCP chain end to end."""

from __future__ import annotations

import socket

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop.runtime_probe import endpoint_host_port, probe_broker, probe_photoshop


def _check_tcp_endpoint(url: str, timeout: float) -> dict:
    try:
        host, port = endpoint_host_port(url)
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "url": url, "host": host, "port": port}
    except (OSError, ValueError) as exc:
        return {"ok": False, "url": url, "error": str(exc)}


@skill_entry
def verify_connection(
    mcp_url: str = "http://127.0.0.1:9765/mcp",
    broker_url: str = "http://127.0.0.1:47391",
    timeout: int = 10,
    **kwargs,
) -> dict:
    """Verify MCP transport, broker health, bridge session, and a real host call."""
    check_timeout = float(min(timeout, 10))
    mcp = _check_tcp_endpoint(mcp_url, check_timeout)
    broker = probe_broker(broker_url, check_timeout)
    photoshop = (
        probe_photoshop(broker_url, check_timeout)
        if broker.get("sessions", 0) > 0
        else {
            "ok": False,
            "error": "Broker has no connected Photoshop bridge session",
        }
    )
    all_ok = bool(mcp["ok"] and broker["ok"] and broker.get("sessions", 0) > 0 and photoshop["ok"])

    return {
        "success": all_ok,
        "summary": "Photoshop MCP chain is ready" if all_ok else "Photoshop MCP chain is incomplete",
        "details": {"mcp": mcp, "broker": broker, "photoshop": photoshop},
        "prompt": (
            "Load a Photoshop skill and execute a typed tool."
            if all_ok
            else "Start the broker, load the generated bridge with UXP Developer Tool, then retry."
        ),
    }


def main(**kwargs) -> dict:
    return verify_connection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
