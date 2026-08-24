"""State-changing and installed-state services for the Photoshop lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dcc_mcp_photoshop.install_contract import (
    INSTALL_EXIT_INSTALL,
    INSTALL_EXIT_OK,
    INSTALL_EXIT_PREFLIGHT,
    INSTALL_EXIT_REQUIRES_RESTART,
    INSTALL_EXIT_VERIFY,
    package_version,
    state_dir,
)
from dcc_mcp_photoshop.install_io import (
    begin_bridge_commit,
    load_receipt,
    receipt_files_match,
    remove_receipt_install,
    stage_bridge,
)
from dcc_mcp_photoshop.install_verification import observe_process_identity, verify_photoshop_rpc


def _uxp_bootstrap_blocker() -> dict[str, Any]:
    """Describe the unavailable bounded host action without inventing a dead command."""
    return {
        "reason": "bounded_photoshop_uxp_bootstrap_unavailable",
        "dependency_issue": "https://github.com/dcc-mcp/adobepy/issues/67",
        "continuation_command": ["dcc-mcp-photoshop", "verify", "--json"],
    }


def _block_unowned_install(report: dict[str, Any], *, staging: Path | None = None) -> tuple[dict[str, Any], int]:
    if staging is not None:
        shutil.rmtree(staging, ignore_errors=True)
    report.update(status="failed", mode="apply", exit_code=INSTALL_EXIT_PREFLIGHT)
    report["steps"][0] = {
        "id": "preflight",
        "status": "failed",
        "message": "Exact receipt ownership is required before Photoshop bridge replacement",
    }
    report["steps"][1] = {"id": "stage_bridge", "status": "blocked"}
    report["steps"][2] = {"id": "verify", "status": "blocked"}
    report["verify"] = {
        "directly_usable": False,
        "failure_stage": "receipt_integrity",
        "failure_reason": "Existing Photoshop bridge state is not the exact receipt-owned closure",
    }
    report["next_steps"] = []
    return report, INSTALL_EXIT_PREFLIGHT


def _capture_previous_receipt(
    report: dict[str, Any], destination: Path, receipt_path: Path
) -> tuple[bool, bytes | None, bool]:
    """Capture an exact prior receipt, or prove the destination is still fresh."""
    installed_state = report.get("installed_state")
    if installed_state == "fresh":
        return not destination.exists() and not receipt_path.exists(), None, True
    if installed_state != "installed":
        return False, None, False
    try:
        receipt_bytes = receipt_path.read_bytes()
    except OSError:
        return False, None, False
    receipt = load_receipt(receipt_path, destination)
    if receipt is None or not receipt_files_match(receipt, destination):
        return False, None, False
    try:
        unchanged = receipt_path.read_bytes() == receipt_bytes
    except OSError:
        unchanged = False
    return unchanged, receipt_bytes if unchanged else None, False


def _previous_state_unchanged(
    *,
    destination: Path,
    receipt_path: Path,
    expected_previous_receipt: bytes | None,
    require_fresh_destination: bool,
) -> bool:
    if require_fresh_destination:
        return not destination.exists() and not receipt_path.exists()
    if expected_previous_receipt is None:
        return False
    try:
        if receipt_path.read_bytes() != expected_previous_receipt:
            return False
    except OSError:
        return False
    receipt = load_receipt(receipt_path, destination)
    return receipt is not None and receipt_files_match(receipt, destination)


def apply_install(
    report: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    replacer: Callable[[Any, Any], Any],
    python_probe: Callable[[str, float], dict[str, Any]],
    broker_probe: Callable[[str, float], dict[str, Any]],
    photoshop_probe: Callable[[str, float], dict[str, Any]],
    process_probe: Callable[[int], dict[str, Any]] = observe_process_identity,
) -> tuple[dict[str, Any], int]:
    """Stage, atomically commit, and verify one receipt-backed bridge install."""
    lifecycle_state = state_dir()
    destination = Path(report["plan"]["bridge"]["destination"])
    receipt_path = Path(report["receipt_path"])
    owned, expected_previous_receipt, require_fresh_destination = _capture_previous_receipt(
        report, destination, receipt_path
    )
    if not owned:
        return _block_unowned_install(report)
    staging, error = stage_bridge(
        executable=Path(report["plan"]["bridge"]["installer"]),
        expected_identity=report["plan"]["bridge"]["installer_identity"],
        state_dir=lifecycle_state,
        token=os.environ["ADOBEPY_TOKEN"],
        runner=runner,
    )
    if staging is None:
        report.update(status="failed", exit_code=INSTALL_EXIT_INSTALL)
        report["steps"][1] = {"id": "stage_bridge", "status": "failed", "message": error}
        report["verify"] = {
            "directly_usable": False,
            "failure_stage": "stage_bridge",
            "failure_reason": error,
        }
        return report, INSTALL_EXIT_INSTALL

    if not _previous_state_unchanged(
        destination=destination,
        receipt_path=receipt_path,
        expected_previous_receipt=expected_previous_receipt,
        require_fresh_destination=require_fresh_destination,
    ):
        return _block_unowned_install(report, staging=staging)
    receipt = {
        "schema_version": 1,
        "dcc_type": "photoshop",
        "adapter_version": report["adapter_version"],
        "core_version": report["core_version"],
        "host": report["plan"]["host"],
        "python": report["plan"]["python"],
        "bridge": report["plan"]["bridge"],
        "bridge_root": str(destination),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    commit_status, commit_error, transaction = begin_bridge_commit(
        staging=staging,
        destination=destination,
        receipt_path=receipt_path,
        receipt=receipt,
        replacer=replacer,
        expected_previous_receipt=expected_previous_receipt,
        require_fresh_destination=require_fresh_destination,
    )
    if commit_status != "ok":
        exit_code = INSTALL_EXIT_REQUIRES_RESTART if commit_status == "requires_restart" else INSTALL_EXIT_INSTALL
        report.update(
            status="requires_restart" if commit_status == "requires_restart" else "failed",
            exit_code=exit_code,
        )
        report["steps"][1] = {"id": "stage_bridge", "status": commit_status, "message": commit_error}
        report["verify"] = {
            "directly_usable": False,
            "failure_stage": "commit",
            "failure_reason": commit_error,
        }
        return report, exit_code
    if transaction is None:
        report.update(status="failed", exit_code=INSTALL_EXIT_INSTALL)
        report["verify"] = {
            "directly_usable": False,
            "failure_stage": "commit",
            "failure_reason": "Bridge commit did not return a verification transaction",
        }
        return report, INSTALL_EXIT_INSTALL

    verification = verify_photoshop_rpc(
        os.environ.get("ADOBEPY_BROKER_URL", "http://127.0.0.1:47391"),
        python_executable=report["plan"]["python"]["executable"],
        expected_host=report["plan"]["host"],
        expected_bridge=report["plan"]["bridge"],
        expected_bridge_root=destination,
        expected_python=report["plan"]["python"],
        python_probe=python_probe,
        broker_probe=broker_probe,
        photoshop_probe=photoshop_probe,
        process_probe=process_probe,
    )
    if verification["directly_usable"]:
        try:
            transaction.finalize()
        except OSError:
            report.update(
                status="requires_restart",
                mode="apply",
                exit_code=INSTALL_EXIT_REQUIRES_RESTART,
            )
            report["steps"][1] = {
                "id": "stage_bridge",
                "status": "requires_restart",
                "message": "Verified bridge backup cleanup requires a Photoshop restart",
            }
            report["verify"] = verification
            return report, INSTALL_EXIT_REQUIRES_RESTART
        report.update(status="ok", mode="apply", exit_code=INSTALL_EXIT_OK)
        report["steps"][0] = {"id": "preflight", "status": "ok"}
        report["steps"][1] = {"id": "stage_bridge", "status": "ok"}
        report["steps"][2] = {"id": "verify", "status": "ok"}
        report["verify"] = verification
        report["next_steps"] = []
        return report, INSTALL_EXIT_OK

    if transaction.moved_previous:
        try:
            transaction.rollback()
        except OSError:
            report.update(status="failed", mode="apply", exit_code=INSTALL_EXIT_INSTALL)
            report["verify"] = {
                "directly_usable": False,
                "failure_stage": "rollback",
                "failure_reason": "The previous Photoshop bridge could not be restored",
            }
            return report, INSTALL_EXIT_INSTALL
        report.update(status="failed", mode="apply", exit_code=INSTALL_EXIT_VERIFY)
        report["steps"][0] = {"id": "preflight", "status": "ok"}
        report["steps"][1] = {"id": "stage_bridge", "status": "rolled_back"}
        report["steps"][2] = {"id": "verify", "status": "failed"}
        report["verify"] = verification
        report["previous_install_restored"] = True
        report["next_steps"] = []
        report["blocker"] = _uxp_bootstrap_blocker()
        return report, INSTALL_EXIT_VERIFY

    transaction.finalize()
    report.update(status="requires_restart", mode="apply", exit_code=INSTALL_EXIT_REQUIRES_RESTART)
    report["steps"][0] = {"id": "preflight", "status": "ok"}
    report["steps"][1] = {"id": "stage_bridge", "status": "ok"}
    report["steps"][2] = {"id": "verify", "status": "requires_host_action"}
    report["verify"] = verification
    report["next_steps"] = []
    report["blocker"] = _uxp_bootstrap_blocker()
    return report, INSTALL_EXIT_REQUIRES_RESTART


def inspect_existing_install(
    *,
    verb: str,
    yes: bool,
    dry_run: bool,
    python_probe: Callable[[str, float], dict[str, Any]],
    broker_probe: Callable[[str, float], dict[str, Any]],
    photoshop_probe: Callable[[str, float], dict[str, Any]],
    process_probe: Callable[[int], dict[str, Any]] = observe_process_identity,
) -> tuple[dict[str, Any], int]:
    """Inspect, verify, or remove only receipt-owned installed state."""
    lifecycle_state = state_dir()
    bridge_root = lifecycle_state / "bridge"
    receipt_path = lifecycle_state / "receipts" / "photoshop.json"
    receipt = load_receipt(receipt_path, bridge_root)
    if receipt and bridge_root.is_dir() and receipt_files_match(receipt, bridge_root):
        installed_state = "installed"
    elif receipt or bridge_root.exists():
        installed_state = "partial"
    else:
        installed_state = "fresh"

    if installed_state == "installed":
        verification = {
            "directly_usable": False,
            "failure_stage": "authentication",
            "failure_reason": "ADOBEPY_TOKEN must be configured in the environment",
        }
    elif installed_state == "partial":
        verification = {
            "directly_usable": False,
            "failure_stage": "receipt_integrity",
            "failure_reason": "The Photoshop bridge and receipt do not form a complete install",
        }
    else:
        verification = {
            "directly_usable": False,
            "failure_stage": "install_state",
            "failure_reason": "No receipt-backed Photoshop bridge is installed",
        }
    if installed_state == "installed" and os.environ.get("ADOBEPY_TOKEN"):
        receipt_python = receipt.get("python")
        receipt_python = receipt_python if isinstance(receipt_python, dict) else {}
        verification = verify_photoshop_rpc(
            os.environ.get("ADOBEPY_BROKER_URL", "http://127.0.0.1:47391"),
            python_executable=receipt_python.get("executable", sys.executable),
            expected_host=receipt.get("host") if isinstance(receipt.get("host"), dict) else None,
            expected_bridge=receipt.get("bridge") if isinstance(receipt.get("bridge"), dict) else None,
            expected_bridge_root=bridge_root,
            expected_python=receipt_python,
            python_probe=python_probe,
            broker_probe=broker_probe,
            photoshop_probe=photoshop_probe,
            process_probe=process_probe,
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "ok" if installed_state != "partial" else "partial",
        "dcc_type": "photoshop",
        "adapter_version": package_version("dcc-mcp-photoshop"),
        "core_version": package_version("dcc-mcp-core"),
        "steps": [{"id": "inspect_receipt", "status": installed_state}],
        "next_steps": [],
        "receipt_path": str(receipt_path) if receipt else None,
        "verify": verification,
        "verb": verb,
        "mode": "plan" if dry_run or (verb == "uninstall" and not yes) else "apply",
        "exit_code": INSTALL_EXIT_OK,
        "installed_state": installed_state,
    }

    if verb == "status":
        return report, INSTALL_EXIT_OK
    if verb == "verify":
        exit_code = INSTALL_EXIT_OK if verification["directly_usable"] else INSTALL_EXIT_VERIFY
        report["status"] = "ok" if exit_code == 0 else "failed"
        report["exit_code"] = exit_code
        report["steps"].append({"id": "verify_photoshop_rpc", "status": report["status"]})
        return report, exit_code
    if not yes or dry_run:
        report["status"] = "planned"
        report["steps"].append({"id": "uninstall", "status": "planned"})
        return report, INSTALL_EXIT_OK
    if installed_state == "partial":
        report.update(status="failed", exit_code=INSTALL_EXIT_PREFLIGHT)
        report["steps"].append(
            {
                "id": "uninstall",
                "status": "blocked",
                "message": "Receipt integrity must be restored before uninstall",
            }
        )
        return report, INSTALL_EXIT_PREFLIGHT
    if receipt is None and installed_state == "fresh":
        report.update(status="ok", exit_code=INSTALL_EXIT_OK, receipt_path=None)
        report["steps"].append({"id": "uninstall", "status": "not_installed"})
        report["verify"] = {
            "directly_usable": False,
            "failure_stage": "not_installed",
            "failure_reason": "No receipt-backed Photoshop bridge is installed",
        }
        return report, INSTALL_EXIT_OK
    if receipt is None:
        report.update(status="failed", exit_code=INSTALL_EXIT_PREFLIGHT)
        report["verify"] = {
            "directly_usable": False,
            "failure_stage": "receipt",
            "failure_reason": "A valid Photoshop install receipt is required",
        }
        return report, INSTALL_EXIT_PREFLIGHT

    remove_status, remove_error = remove_receipt_install(
        bridge_root=bridge_root,
        receipt_path=receipt_path,
    )
    if remove_status != "ok":
        exit_code = INSTALL_EXIT_REQUIRES_RESTART if remove_status == "requires_restart" else INSTALL_EXIT_INSTALL
        report.update(status=remove_status, exit_code=exit_code)
        report["steps"].append({"id": "uninstall", "status": remove_status, "message": remove_error})
        return report, exit_code
    report.update(status="ok", exit_code=INSTALL_EXIT_OK, receipt_path=None, installed_state="fresh")
    report["steps"].append({"id": "uninstall", "status": "ok"})
    report["verify"] = {
        "directly_usable": False,
        "failure_stage": "not_installed",
        "failure_reason": "The receipt-owned Photoshop bridge was uninstalled",
    }
    return report, INSTALL_EXIT_OK
