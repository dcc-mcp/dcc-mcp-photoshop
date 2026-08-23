"""Preflight and planning for the canonical Photoshop install lifecycle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dcc_mcp_photoshop.install_contract import (
    INSTALL_EXIT_ACQUIRE,
    INSTALL_EXIT_OK,
    INSTALL_EXIT_PREFLIGHT,
    MIN_CORE_VERSION,
    MIN_PYTHON_VERSION,
    package_version,
    state_dir,
    version_tuple,
)
from dcc_mcp_photoshop.install_discovery import discover_photoshop_executable, host_version
from dcc_mcp_photoshop.install_io import load_receipt, receipt_files_match


def _host_supported(version: str | None) -> bool:
    if not version:
        return False
    try:
        major = int(version.split(".", 1)[0])
    except ValueError:
        return False
    return major >= 2022 if major >= 2000 else major >= 23


def _python_version(executable: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    version = (result.stdout or result.stderr).strip()
    return version[len("Python ") :] if version.startswith("Python ") else version


def build_install_report(*, verb: str, dcc_path: str, python: str, dry_run: bool) -> tuple[dict[str, Any], int]:
    """Build a read-only install or upgrade plan and run all preflight checks."""
    lifecycle_state = state_dir()
    receipt_path = lifecycle_state / "receipts" / "photoshop.json"
    bridge_root = lifecycle_state / "bridge"
    receipt = load_receipt(receipt_path, bridge_root)
    receipt_host = receipt.get("host") if receipt else None
    receipt_host = receipt_host if isinstance(receipt_host, dict) else {}
    receipt_python = receipt.get("python") if receipt else None
    receipt_python = receipt_python if isinstance(receipt_python, dict) else {}
    if dcc_path:
        host = Path(dcc_path).expanduser()
        detected_host_version = host_version(host)
    elif verb == "upgrade" and receipt:
        host = Path(receipt_host.get("executable", "")).expanduser()
        detected_host_version = receipt_host.get("version")
    else:
        discovered_host, detected_host_version = discover_photoshop_executable()
        host = discovered_host or Path()
    if python:
        interpreter = Path(python).expanduser()
    elif verb == "upgrade" and receipt:
        interpreter = Path(receipt_python.get("executable", sys.executable)).expanduser()
    else:
        interpreter = Path(sys.executable)
    python_version = _python_version(interpreter) if interpreter.is_file() else None
    core_version = package_version("dcc-mcp-core")
    adobepy_cli_value = os.environ.get("ADOBEPY_CLI", "")
    adobepy_cli = Path(adobepy_cli_value).expanduser() if adobepy_cli_value else None
    if receipt and bridge_root.is_dir() and receipt_files_match(receipt, bridge_root):
        installed_state = "installed"
    elif receipt or bridge_root.exists():
        installed_state = "partial"
    else:
        installed_state = "fresh"

    failures: list[tuple[str, str]] = []
    broker_url = os.environ.get("ADOBEPY_BROKER_URL", "http://127.0.0.1:47391")
    parsed_broker = urlparse(broker_url)
    if parsed_broker.username is not None or parsed_broker.password is not None:
        failures.append(("security", "Broker URL credentials are not supported; configure authentication separately"))
    if version_tuple(core_version) < version_tuple(MIN_CORE_VERSION):
        failures.append(("core_version", f"dcc-mcp-core {MIN_CORE_VERSION} or newer is required"))
    if not host.is_file():
        failures.append(("preflight", "Photoshop executable was not found"))
    elif not _host_supported(detected_host_version):
        failures.append(("preflight", "Photoshop 2022 or newer is required"))
    if python_version is None:
        failures.append(("preflight", "Target Python could not be executed"))
    elif version_tuple(python_version)[:2] < MIN_PYTHON_VERSION:
        failures.append(("preflight", "Python 3.8 or newer is required"))
    if adobepy_cli is None or not adobepy_cli.is_file():
        failures.append(("acquire", "A supported adobepy CLI is required to stage the UXP bridge"))
    if not os.environ.get("ADOBEPY_TOKEN"):
        failures.append(("preflight", "ADOBEPY_TOKEN must be configured in the environment"))

    failure_stage, failure_reason = failures[0] if failures else (None, None)
    exit_code = (
        INSTALL_EXIT_ACQUIRE
        if failure_stage == "acquire"
        else INSTALL_EXIT_PREFLIGHT
        if failure_stage
        else INSTALL_EXIT_OK
    )
    status = "failed" if failure_stage else "planned"
    retry_command = ["dcc-mcp-photoshop", verb, "--json", "--dry-run"]
    if host.is_file():
        retry_command.extend(["--dcc-path", str(host)])
    if interpreter.is_file():
        retry_command.extend(["--python", str(interpreter)])
    next_steps = (
        [
            {
                "id": f"retry-{verb}-plan",
                "description": f"Retry the canonical Photoshop {verb} plan after resolving preflight",
                "command": retry_command,
                "why": failure_reason,
            }
        ]
        if failure_stage
        else []
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "dcc_type": "photoshop",
        "adapter_version": package_version("dcc-mcp-photoshop"),
        "core_version": core_version,
        "steps": [
            {"id": "preflight", "status": "ok" if not failure_stage else "failed"},
            {"id": "stage_bridge", "status": "planned" if not failure_stage else "blocked"},
            {"id": "verify", "status": "planned" if not failure_stage else "blocked"},
        ],
        "next_steps": next_steps,
        "receipt_path": str(receipt_path),
        "verify": {
            "directly_usable": False,
            "failure_stage": failure_stage or "not_installed",
            "failure_reason": failure_reason or "Dry-run does not change the installed state",
        },
        "verb": verb,
        "mode": "plan" if dry_run or verb in {"install", "upgrade"} else "inspect",
        "exit_code": exit_code,
        "installed_state": installed_state,
        "plan": {
            "action": "upgrade" if verb == "upgrade" else "repair" if installed_state != "fresh" else "install",
            "host": {"executable": str(host), "version": detected_host_version},
            "python": {"executable": str(interpreter), "version": python_version},
            "bridge": {
                "installer": str(adobepy_cli) if adobepy_cli else None,
                "destination": str(bridge_root),
            },
            "requirements": {
                "minimum_core_version": MIN_CORE_VERSION,
                "minimum_python_version": "3.8",
                "minimum_photoshop_version": "2022",
            },
        },
    }
    return report, exit_code
