"""Canonical Install SOP v1 entry point for the Photoshop adapter."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Callable

from dcc_mcp_photoshop.install_contract import INSTALL_EXIT_INSTALL, INSTALL_EXIT_OK, package_version
from dcc_mcp_photoshop.install_planning import build_install_report
from dcc_mcp_photoshop.install_service import apply_install, inspect_existing_install
from dcc_mcp_photoshop.install_verification import observe_process_identity, probe_target_import
from dcc_mcp_photoshop.runtime_probe import probe_broker, probe_photoshop


def run_install_lifecycle(
    args: Any,
    *,
    external_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    atomic_replace: Callable[[Any, Any], Any] = os.replace,
    python_probe: Callable[[str, float], dict[str, Any]] = probe_target_import,
    broker_probe: Callable[[str, float], dict[str, Any]] = probe_broker,
    photoshop_probe: Callable[[str, float], dict[str, Any]] = probe_photoshop,
    process_probe: Callable[[int], dict[str, Any]] = observe_process_identity,
) -> int:
    """Execute the public lifecycle command and emit one result document."""
    try:
        if args.command in {"status", "verify", "uninstall"}:
            report, exit_code = inspect_existing_install(
                verb=args.command,
                yes=args.yes,
                dry_run=args.dry_run,
                python_probe=python_probe,
                broker_probe=broker_probe,
                photoshop_probe=photoshop_probe,
                process_probe=process_probe,
            )
        else:
            report, exit_code = build_install_report(
                verb=args.command,
                dcc_path=args.dcc_path,
                python=args.python,
                dry_run=args.dry_run,
            )
        if exit_code == INSTALL_EXIT_OK and args.command in {"install", "upgrade"} and args.yes and not args.dry_run:
            report, exit_code = apply_install(
                report,
                runner=external_runner,
                replacer=atomic_replace,
                python_probe=python_probe,
                broker_probe=broker_probe,
                photoshop_probe=photoshop_probe,
                process_probe=process_probe,
            )
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        if isinstance(exc, FileNotFoundError):
            error_type = "invalid_executable"
        elif isinstance(exc, OSError):
            error_type = "os_error"
        elif isinstance(exc, KeyError):
            error_type = "missing_field"
        elif isinstance(exc, TypeError):
            error_type = "invalid_type"
        elif isinstance(exc, ValueError):
            error_type = "invalid_value"
        else:
            error_type = "subprocess_error"
        exit_code = INSTALL_EXIT_INSTALL
        report = {
            "schema_version": 1,
            "status": "failed",
            "dcc_type": "photoshop",
            "adapter_version": package_version("dcc-mcp-photoshop"),
            "core_version": package_version("dcc-mcp-core"),
            "steps": [{"id": "lifecycle", "status": "failed"}],
            "next_steps": [],
            "receipt_path": None,
            "verify": {
                "directly_usable": False,
                "failure_stage": "internal_error",
                "failure_reason": "The Photoshop lifecycle could not complete safely",
                "error_type": error_type,
            },
            "verb": getattr(args, "command", "unknown"),
            "mode": "plan",
            "exit_code": exit_code,
        }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Photoshop {args.command}: {report['status']} (exit {exit_code})")
    return exit_code
