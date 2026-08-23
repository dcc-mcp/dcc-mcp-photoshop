"""Verify-to-usable checks for the installed Photoshop bridge."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Callable, Dict

from dcc_mcp_photoshop.runtime_probe import probe_broker, probe_photoshop

Probe = Callable[[str, float], Dict[str, Any]]
PythonProbe = Callable[[str, float], Dict[str, Any]]


def probe_target_import(executable: str, timeout: float) -> dict[str, Any]:
    """Import the adapter and typed Photoshop facade in the selected Python."""
    env = os.environ.copy()
    for name in ("ADOBEPY_TOKEN", "ADOBE_TOKEN"):
        env.pop(name, None)
    try:
        result = subprocess.run(
            [executable, "-c", "import dcc_mcp_photoshop; from adobe.photoshop import Photoshop"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return {"ok": False}
    return {"ok": result.returncode == 0}


def verify_photoshop_rpc(
    broker_url: str,
    *,
    python_executable: str,
    python_probe: PythonProbe = probe_target_import,
    broker_probe: Probe = probe_broker,
    photoshop_probe: Probe = probe_photoshop,
) -> dict[str, Any]:
    """Require broker health, a UXP session, and a typed Photoshop call."""
    target_import = python_probe(python_executable, 10.0)
    if not target_import.get("ok"):
        return {
            "directly_usable": False,
            "failure_stage": "target_import",
            "failure_reason": "The selected Python cannot import the adapter and typed Photoshop facade",
        }
    broker = broker_probe(broker_url, 5.0)
    if not broker.get("ok"):
        return {
            "directly_usable": False,
            "failure_stage": "broker_health",
            "failure_reason": "The adobepy broker health probe failed",
        }
    if int(broker.get("sessions", 0)) < 1:
        return {
            "directly_usable": False,
            "failure_stage": "uxp_session",
            "failure_reason": "The broker has no connected Photoshop UXP session",
        }
    photoshop = photoshop_probe(broker_url, 5.0)
    if not photoshop.get("ok"):
        return {
            "directly_usable": False,
            "failure_stage": "photoshop_rpc",
            "failure_reason": "A real typed Photoshop RPC failed",
        }
    return {
        "directly_usable": True,
        "failure_stage": None,
        "failure_reason": None,
    }
