"""Preflight and planning for the canonical Photoshop install lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
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
from dcc_mcp_photoshop.install_verification import probe_target_import


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


def _canonical_host_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file() or resolved.is_symlink() or resolved.stat().st_size < 0:
        return False
    name = resolved.name
    if os.name == "nt":
        return name.casefold() == "photoshop.exe" and bool(host_version(resolved.parent))
    return bool(
        re.fullmatch(r"Adobe Photoshop (?:20\d{2}|\d{2}(?:\.\d+)?)", name, re.IGNORECASE) and host_version(resolved)
    )


def _adobepy_cli_identity(path: Path | None, sdk_version: str | None) -> dict[str, Any] | None:
    if path is None or not version_tuple(sdk_version):
        return None
    try:
        resolved = path.resolve()
        contents = resolved.read_bytes()
        manifest_path = resolved.parent.parent / "package-manifest.json"
        if manifest_path.stat().st_size > 65_536:
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    expected_names = {"adobepy", "adobepy.exe"}
    relative_cli = f"bin/{resolved.name}"
    includes = manifest.get("includes") if isinstance(manifest, dict) else None
    includes_are_safe = bool(
        isinstance(includes, list)
        and includes
        and all(
            isinstance(item, str)
            and 0 < len(item) <= 256
            and "\\" not in item
            and not PurePosixPath(item).is_absolute()
            and ".." not in PurePosixPath(item).parts
            for item in includes
        )
    )
    if (
        not contents
        or resolved.name.casefold() not in expected_names
        or resolved.is_symlink()
        or resolved.parent.name != "bin"
        or not isinstance(manifest, dict)
        or manifest.get("name") != "adobepy"
        or manifest.get("version") != sdk_version
        or not isinstance(manifest.get("runtime"), str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,64}", manifest["runtime"]) is None
        or not includes_are_safe
        or relative_cli not in includes
        or re.fullmatch(
            rf"adobepy-{re.escape(sdk_version)}-[A-Za-z0-9._-]+",
            resolved.parent.parent.name,
        )
        is None
    ):
        return None
    return {
        "executable": str(resolved),
        "version": sdk_version,
        "runtime": manifest["runtime"],
        "bytes": len(contents),
        "sha256": hashlib.sha256(contents).hexdigest(),
    }


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
    target_import = probe_target_import(str(interpreter), 10.0) if python_version else {"ok": False}
    adobepy_cli_value = os.environ.get("ADOBEPY_CLI", "")
    adobepy_cli = Path(adobepy_cli_value).expanduser() if adobepy_cli_value else None
    target_modules = target_import.get("modules") if isinstance(target_import, dict) else None
    adobepy_module = target_modules.get("adobepy") if isinstance(target_modules, dict) else None
    adobepy_sdk_version = adobepy_module.get("version") if isinstance(adobepy_module, dict) else None
    adobepy_identity = _adobepy_cli_identity(adobepy_cli, adobepy_sdk_version)
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
    elif not _canonical_host_path(host):
        failures.append(("preflight", "--dcc-path must select a canonical Photoshop executable"))
    elif not _host_supported(detected_host_version):
        failures.append(("preflight", "Photoshop 2022 or newer is required"))
    if python_version is None:
        failures.append(("preflight", "Target Python could not be executed"))
    elif version_tuple(python_version)[:2] < MIN_PYTHON_VERSION:
        failures.append(("preflight", "Python 3.8 or newer is required"))
    elif target_import.get("ok") is not True:
        failures.append(("preflight", "Target Python imports are not owned by their selected distributions"))
    if adobepy_identity is None:
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
    broker_authority = None
    try:
        if parsed_broker.hostname and parsed_broker.port:
            broker_authority = f"{parsed_broker.hostname}:{parsed_broker.port}"
    except ValueError:
        broker_authority = None
    doctor_command = (
        [
            adobepy_identity["executable"],
            "doctor",
            "--broker",
            broker_authority,
            "--python",
            str(interpreter.resolve()),
            "--json",
        ]
        if adobepy_identity and broker_authority and interpreter.is_file()
        else None
    )
    next_steps = (
        [
            {
                "id": "diagnose-adobepy-runtime",
                "description": "Run the trusted adobepy doctor against the selected broker and Python",
                "command": doctor_command,
                "why": "The missing broker token must be recovered from the operator-owned broker before installation can continue",
            }
        ]
        if failure_reason == "ADOBEPY_TOKEN must be configured in the environment" and doctor_command
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
            "host": {
                "executable": str(host.resolve()) if host.is_file() else str(host),
                "version": detected_host_version,
            },
            "python": {
                "executable": str(interpreter.resolve()) if interpreter.is_file() else str(interpreter),
                "version": python_version,
                "modules": target_import.get("modules", {}),
            },
            "bridge": {
                "installer": adobepy_identity["executable"] if adobepy_identity else None,
                "installer_version": adobepy_identity["version"] if adobepy_identity else None,
                "installer_runtime": adobepy_identity["runtime"] if adobepy_identity else None,
                "installer_bytes": adobepy_identity["bytes"] if adobepy_identity else None,
                "installer_sha256": adobepy_identity["sha256"] if adobepy_identity else None,
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
