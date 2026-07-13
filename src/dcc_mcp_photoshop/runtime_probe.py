"""Runtime probes for the adobepy-backed Photoshop adapter."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def probe_broker(broker_url: str, timeout: float) -> dict:
    """Return the broker health payload or a structured failure."""
    url = f"{broker_url.rstrip('/')}/health"
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - the probe reports transport failures
        return {"ok": False, "url": url, "sessions": 0, "error": str(exc)}

    sessions = int(payload.get("sessions", 0))
    return {
        "ok": payload.get("status") == "ok",
        "url": url,
        "sessions": sessions,
        "status": payload.get("status", "unknown"),
    }


def probe_photoshop(broker_url: str, timeout: float) -> dict:
    """Execute a real host call through the broker."""
    try:
        from adobe.photoshop import Photoshop  # noqa: PLC0415

        app = Photoshop(
            broker_url=broker_url,
            token=os.environ.get("ADOBEPY_TOKEN"),
            target=os.environ.get("ADOBEPY_TARGET"),
            timeout=timeout,
        )
        return {"ok": True, "version": app.version}
    except Exception as exc:  # noqa: BLE001 - the probe reports host failures
        return {"ok": False, "error": str(exc)}


def endpoint_host_port(url: str) -> tuple[str, int]:
    """Extract a TCP target from an HTTP endpoint."""
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"Invalid endpoint URL: {url}")
    return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
