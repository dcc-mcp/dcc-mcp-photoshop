"""Canonical Install SOP v1 entry point for the Photoshop adapter."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Callable

from dcc_mcp_photoshop.install_contract import INSTALL_EXIT_OK
from dcc_mcp_photoshop.install_planning import build_install_report
from dcc_mcp_photoshop.install_service import apply_install, inspect_existing_install
from dcc_mcp_photoshop.install_verification import probe_target_import
from dcc_mcp_photoshop.runtime_probe import probe_broker, probe_photoshop


def run_install_lifecycle(
    args: Any,
    *,
    external_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    atomic_replace: Callable[[Any, Any], Any] = os.replace,
    python_probe: Callable[[str, float], dict[str, Any]] = probe_target_import,
    broker_probe: Callable[[str, float], dict[str, Any]] = probe_broker,
    photoshop_probe: Callable[[str, float], dict[str, Any]] = probe_photoshop,
) -> int:
    """Execute the public lifecycle command and emit one result document."""
    if args.command in {"status", "verify", "uninstall"}:
        report, exit_code = inspect_existing_install(
            verb=args.command,
            yes=args.yes,
            dry_run=args.dry_run,
            python_probe=python_probe,
            broker_probe=broker_probe,
            photoshop_probe=photoshop_probe,
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
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Photoshop {args.command}: {report['status']} (exit {exit_code})")
    return exit_code
