"""Preflight and planning for the canonical Photoshop install lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dcc_mcp_photoshop.install_contract import (
    ADOBEPY_MIN_VERSION,
    ADOBEPY_MODULE,
    ADOBEPY_MODULE_ENTRY_POINT,
    ADOBEPY_MODULE_PROVENANCE,
    ADOBEPY_SPECIFIER,
    ALLOW_UNVERIFIED_HOST_ENV,
    CORE_SPECIFIER,
    INSTALL_EXIT_ACQUIRE,
    INSTALL_EXIT_OK,
    INSTALL_EXIT_PREFLIGHT,
    MIN_CORE_VERSION,
    MIN_PYTHON_VERSION,
    package_version,
    satisfies_adobepy_floor,
    satisfies_adobepy_specifier,
    satisfies_core_specifier,
    state_dir,
    version_tuple,
)
from dcc_mcp_photoshop.install_discovery import (
    attest_photoshop_executable,
    discover_photoshop_executable,
    host_provenance_reason,
    path_uses_link,
)
from dcc_mcp_photoshop.install_io import (
    adobepy_bridge_argv,
    adobepy_module_available,
    load_receipt,
    receipt_files_match,
)
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


# Releases page used when no row below matches the current platform. Keep it pinned to
# the project's releases index rather than a mutable `latest` download URL.
_ADOBEPY_RELEASES_URL = "https://github.com/dcc-mcp/adobepy/releases"
_ADOBEPY_CLI_RELEASES = {
    ("0.6.2", "windows-x64"): {
        "asset_name": "adobepy-0.6.2-windows-x64.zip",
        "asset_sha256": "9ef9abb5e034359f12e9ce248b0030e38d34c76df343eb2713f18036068719a7",
        "release_url": "https://github.com/dcc-mcp/adobepy/releases/tag/adobepy-v0.6.2",
        "cli_name": "adobepy.exe",
        "cli_bytes": 2_974_720,
        "cli_sha256": "c02f28f07705b69a4f97f9f6639f0f80d1f5292115446801fbd92423336301aa",
        "manifest_bytes": 663,
        "manifest_sha256": "3f0cf14b44b1d4c7d98b0175152e7ea58fc3edb92bd61e84983b3ad39de6b554",
    }
}


def _adobepy_platform_key() -> str | None:
    machine = platform.machine().casefold()
    if os.name == "nt" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    return None


def _file_sha256(path: Path, expected_size: int) -> str | None:
    try:
        if path.stat().st_size != expected_size:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _adobepy_cli_identity(path: Path | None, sdk_version: str | None) -> dict[str, Any] | None:
    platform_key = _adobepy_platform_key()
    release = _ADOBEPY_CLI_RELEASES.get((sdk_version, platform_key))
    if path is None or not version_tuple(sdk_version) or release is None:
        return None
    try:
        if path_uses_link(path):
            return None
        resolved = path.resolve(strict=True)
        manifest_path = resolved.parent.parent / "package-manifest.json"
        if path_uses_link(manifest_path):
            return None
        if _file_sha256(resolved, release["cli_bytes"]) != release["cli_sha256"]:
            return None
        if _file_sha256(manifest_path, release["manifest_bytes"]) != release["manifest_sha256"]:
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    relative_cli = f"bin/{resolved.name}"
    includes = manifest.get("includes") if isinstance(manifest, dict) else None
    if (
        resolved.name != release["cli_name"]
        or resolved.parent.name != "bin"
        or resolved.parent.parent.name != f"adobepy-{sdk_version}-{platform_key}"
        or not isinstance(manifest, dict)
        or manifest.get("name") != "adobepy"
        or manifest.get("version") != sdk_version
        or manifest.get("runtime") != platform_key
        or not isinstance(includes, list)
        or relative_cli not in includes
    ):
        return None
    return {
        "executable": str(resolved),
        "version": sdk_version,
        "runtime": platform_key,
        "bytes": release["cli_bytes"],
        "sha256": release["cli_sha256"],
        "manifest_path": str(manifest_path.resolve()),
        "manifest_bytes": release["manifest_bytes"],
        "manifest_sha256": release["manifest_sha256"],
        "release_asset": release["asset_name"],
        "release_asset_sha256": release["asset_sha256"],
        "release_url": release["release_url"],
        "provenance": "official_checksum_release",
    }


def _adobepy_module_identity(interpreter: Path, sdk_version: str | None) -> dict[str, Any] | None:
    """Describe the wheel-only bridge installer: ``<interpreter> -m adobe``.

    The PyPI ``adobepy`` wheel installs the ``adobe`` import package and no standalone
    executable, so a wheel-only install has nothing to checksum. This identity records
    the argv prefix that will be executed and is re-verified immediately before use.
    """
    if not satisfies_adobepy_floor(sdk_version or "") or not adobepy_module_available(interpreter):
        return None
    try:
        resolved = interpreter.resolve(strict=True)
    except OSError:
        return None
    return {
        "executable": str(resolved),
        "version": sdk_version,
        "runtime": _adobepy_platform_key(),
        "module": ADOBEPY_MODULE,
        "entry_point": ADOBEPY_MODULE_ENTRY_POINT,
        # argv prefix; `adobepy_bridge_argv` appends the install-bridge arguments.
        "command_prefix": [str(resolved), "-m", ADOBEPY_MODULE],
        "bytes": None,
        "sha256": None,
        "manifest_path": None,
        "manifest_bytes": None,
        "manifest_sha256": None,
        "release_asset": None,
        "release_asset_sha256": None,
        "release_url": None,
        "provenance": ADOBEPY_MODULE_PROVENANCE,
    }


def resolve_adobepy_installer(
    *,
    configured: Path | None,
    interpreter: Path,
    sdk_version: str | None,
    on_path: str | None = None,
) -> dict[str, Any] | None:
    """Select the bridge installer, preferring the official CLI over the wheel entry point.

    Resolution order:

    1. ``ADOBEPY_CLI`` — an explicit operator pin. It is authoritative: if it does not
       verify against the checksum release table the install fails instead of silently
       falling through to something less trusted.
    2. An ``adobepy`` executable on ``PATH`` — still verified against the same table.
    3. ``<interpreter> -m adobe`` — the wheel-only fallback, used only when no
       executable was configured or found at all.

    Returns ``None`` when no surface is provable, which the caller reports as an
    actionable acquire failure.
    """
    candidates: list[Path] = []
    if configured is not None:
        candidates.append(configured)
    elif on_path:
        candidates.append(Path(on_path))
    for candidate in candidates:
        identity = _adobepy_cli_identity(candidate, sdk_version)
        if identity is not None:
            return identity
        # A configured or PATH-visible executable that fails verification is an error,
        # never a reason to fall back: that would let a replaced binary downgrade the
        # checksum path to the unverified module path.
        return None
    return _adobepy_module_identity(interpreter, sdk_version)


def _adobepy_release_hint() -> str:
    """Name the platform bundle to download, or the releases page when unlisted."""
    release = _ADOBEPY_CLI_RELEASES.get((ADOBEPY_MIN_VERSION, _adobepy_platform_key()))
    if release is None:
        return f"Download an adobepy {ADOBEPY_MIN_VERSION} runtime bundle from {_ADOBEPY_RELEASES_URL}"
    return (
        f"Download {release['asset_name']} from {release['release_url']} "
        f"(SHA-256 {release['asset_sha256']}) and set ADOBEPY_CLI to the extracted "
        f"{release['cli_name']}"
    )


def adobepy_acquire_failure(cli_configured: bool) -> str:
    """Explain how to obtain a bridge installer when none is provable."""
    steps = [_adobepy_release_hint()]
    if cli_configured:
        steps.append(
            "ADOBEPY_CLI is set but is not the pinned official release; point it at the extracted CLI from that bundle"
        )
    else:
        # With only the PyPI wheel installed there is no executable to find, so the
        # pure-Python entry point is the surface to check first.
        steps.append(f"run `python -m adobe doctor` to check the wheel-only entry point ({_ADOBEPY_RELEASES_URL})")
    return "A supported adobepy CLI is required to stage the UXP bridge. " + "; ".join(steps) + "."


# How the operator accepted an unverified host, so the report never credits the wrong mechanism.
_UNVERIFIED_HOST_SOURCES = {
    "flag": "--allow-unverified-host",
    "environment": ALLOW_UNVERIFIED_HOST_ENV,
}


def _host_provenance_failure(host: Path, *, allow_unverified_host: bool) -> str:
    """Name the provenance check that rejected the host so the report is actionable."""
    reason = host_provenance_reason(host, allow_unverified=allow_unverified_host)
    return (
        "Photoshop executable lacks valid Adobe product provenance"
        if reason is None
        else f"Photoshop executable lacks valid Adobe product provenance: {reason}"
    )


def _host_provenance_warnings(
    host_identity: dict[str, Any] | None,
    *,
    allow_unverified_source: str | None,
) -> list[dict[str, Any]]:
    """Describe host facts that were accepted only because the operator opted in."""
    if not host_identity or host_identity.get("signature") != "authenticode_hash_mismatch":
        return []
    return [
        {
            "code": "host_signature_hash_mismatch",
            "stage": "preflight",
            "accepted_by": _UNVERIFIED_HOST_SOURCES.get(allow_unverified_source or "", "unknown"),
            "message": (
                "The selected Photoshop executable reports an Adobe signer and Adobe product "
                "metadata, but its Authenticode hash no longer matches its bytes "
                f"(status={host_identity.get('signature_status')}). The host package was likely "
                "repackaged; provenance could not be proven and was accepted on operator request."
            ),
        }
    ]


def build_install_report(
    *,
    verb: str,
    dcc_path: str,
    python: str,
    dry_run: bool,
    allow_unverified_host: bool = False,
    allow_unverified_source: str | None = None,
) -> tuple[dict[str, Any], int]:
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
        host_source = "flag"
    elif verb == "upgrade" and receipt:
        host = Path(receipt_host.get("executable", "")).expanduser()
        host_source = "receipt"
    else:
        discovered_host, _layout_version = discover_photoshop_executable()
        host = discovered_host or Path()
        host_source = "discovery"
    host_identity = (
        attest_photoshop_executable(host, allow_unverified=allow_unverified_host) if host.is_file() else None
    )
    detected_host_version = host_identity.get("version") if host_identity else None
    if python:
        interpreter = Path(python).expanduser()
        python_source = "flag"
    elif os.environ.get("DCC_MCP_INSTALL_PYTHON"):
        interpreter = Path(os.environ["DCC_MCP_INSTALL_PYTHON"]).expanduser()
        python_source = "environment"
    elif verb == "upgrade" and receipt:
        interpreter = Path(receipt_python.get("executable", sys.executable)).expanduser()
        python_source = "receipt"
    else:
        interpreter = Path(sys.executable)
        python_source = "current_process"
    python_version = _python_version(interpreter) if interpreter.is_file() else None
    process_core_version = package_version("dcc-mcp-core")
    target_import = probe_target_import(str(interpreter), 10.0) if python_version else {"ok": False}
    adobepy_cli_value = os.environ.get("ADOBEPY_CLI", "")
    adobepy_cli = Path(adobepy_cli_value).expanduser() if adobepy_cli_value else None
    target_modules = target_import.get("modules") if isinstance(target_import, dict) else None
    target_core = target_modules.get("core") if isinstance(target_modules, dict) else None
    target_core_version = target_core.get("version") if isinstance(target_core, dict) else None
    core_version = target_core_version or process_core_version
    adobepy_module = target_modules.get("adobepy") if isinstance(target_modules, dict) else None
    adobepy_sdk_version = adobepy_module.get("version") if isinstance(adobepy_module, dict) else None
    adobepy_identity = resolve_adobepy_installer(
        configured=adobepy_cli,
        interpreter=interpreter,
        sdk_version=adobepy_sdk_version,
        on_path=shutil.which("adobepy"),
    )
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
    target_import_error = target_import.get("error_type") if isinstance(target_import, dict) else None
    if (
        not satisfies_core_specifier(process_core_version)
        or not satisfies_core_specifier(core_version)
        or target_import_error == "core_version_out_of_range"
    ):
        failures.append(("core_version", f"dcc-mcp-core {CORE_SPECIFIER} is required"))
    if not host.is_file():
        failures.append(("preflight", "Photoshop executable was not found"))
    elif host_identity is None:
        failures.append(("preflight", _host_provenance_failure(host, allow_unverified_host=allow_unverified_host)))
    elif not _host_supported(detected_host_version):
        failures.append(("preflight", "Photoshop 2022 or newer is required"))
    if python_version is None:
        failures.append(("preflight", "Target Python could not be executed"))
    elif version_tuple(python_version)[:2] < MIN_PYTHON_VERSION:
        failures.append(("preflight", "Python 3.8 or newer is required"))
    elif target_import.get("ok") is not True:
        failures.append(("preflight", "Target Python imports are not owned by their selected distributions"))
    if adobepy_identity is None:
        failures.append(("acquire", adobepy_acquire_failure(adobepy_cli is not None)))
    elif adobepy_identity.get("provenance") != ADOBEPY_MODULE_PROVENANCE and not satisfies_adobepy_specifier(
        adobepy_sdk_version or ""
    ):
        # The wheel-only surface is gated by the version floor in its own identity check;
        # only the checksummed CLI surface is held to the exact pin.
        failures.append(("acquire", f"adobepy {ADOBEPY_SPECIFIER} is required"))
    if not os.environ.get("ADOBEPY_TOKEN"):
        failures.append(("preflight", "ADOBEPY_TOKEN must be configured in the environment"))

    warnings = _host_provenance_warnings(host_identity, allow_unverified_source=allow_unverified_source)

    failure_stage, failure_reason = failures[0] if failures else (None, None)
    exit_code = (
        INSTALL_EXIT_ACQUIRE
        if failure_stage == "acquire"
        else INSTALL_EXIT_PREFLIGHT
        if failure_stage
        else INSTALL_EXIT_OK
    )
    status = "failed" if failure_stage else "planned"
    next_steps: list[dict[str, Any]] = []
    host_plan = dict(
        host_identity
        or {
            "executable": str(host.resolve()) if host.is_file() else str(host),
            "version": detected_host_version,
        }
    )
    host_plan["resolution_source"] = host_source
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "warnings": warnings,
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
            "host": host_plan,
            "python": {
                "executable": str(interpreter.resolve()) if interpreter.is_file() else str(interpreter),
                "version": python_version,
                "resolution_source": python_source,
                "modules": target_import.get("modules", {}),
            },
            "bridge": {
                "installer": adobepy_identity["executable"] if adobepy_identity else None,
                "installer_version": adobepy_identity["version"] if adobepy_identity else None,
                "installer_runtime": adobepy_identity["runtime"] if adobepy_identity else None,
                "installer_bytes": adobepy_identity["bytes"] if adobepy_identity else None,
                "installer_sha256": adobepy_identity["sha256"] if adobepy_identity else None,
                "installer_manifest": adobepy_identity["manifest_path"] if adobepy_identity else None,
                "installer_manifest_bytes": adobepy_identity["manifest_bytes"] if adobepy_identity else None,
                "installer_manifest_sha256": adobepy_identity["manifest_sha256"] if adobepy_identity else None,
                "installer_release_asset": adobepy_identity["release_asset"] if adobepy_identity else None,
                "installer_release_asset_sha256": (
                    adobepy_identity["release_asset_sha256"] if adobepy_identity else None
                ),
                "installer_release_url": adobepy_identity["release_url"] if adobepy_identity else None,
                "installer_provenance": adobepy_identity["provenance"] if adobepy_identity else None,
                "installer_module": adobepy_identity.get("module") if adobepy_identity else None,
                "installer_command": adobepy_bridge_argv(adobepy_identity) if adobepy_identity else None,
                "installer_identity": adobepy_identity,
                "destination": str(bridge_root),
            },
            "requirements": {
                "core_specifier": CORE_SPECIFIER,
                "adobepy_specifier": ADOBEPY_SPECIFIER,
                "minimum_core_version": MIN_CORE_VERSION,
                "minimum_python_version": "3.8",
                "minimum_photoshop_version": "2022",
            },
        },
    }
    if failure_reason == "ADOBEPY_TOKEN must be configured in the environment":
        continuation = [
            "dcc-mcp-photoshop",
            verb,
            "--json",
            "--dcc-path",
            str(host.resolve()),
            "--python",
            str(interpreter.resolve()),
        ]
        if dry_run:
            continuation.append("--dry-run")
        report["blocker"] = {
            "reason": "operator_broker_token_required",
            "configuration": "ADOBEPY_TOKEN",
            "continuation_command": continuation,
        }
    return report, exit_code
