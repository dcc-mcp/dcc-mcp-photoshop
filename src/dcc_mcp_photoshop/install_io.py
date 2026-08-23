"""Filesystem and external-process ownership for the Photoshop installer."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from dcc_mcp_core.install_lifecycle import inspect_install_root

ExternalRunner = Callable[..., subprocess.CompletedProcess]


def _contains_secret(value: str, secret: str) -> bool:
    return bool(secret and secret in value)


def _replace_with_retry(replacer: Callable[[Any, Any], Any], source: Any, destination: Any) -> None:
    """Bound transient Windows sharing violations around an atomic rename."""
    for attempt in range(3):
        try:
            replacer(source, destination)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))


def stage_bridge(
    *,
    executable: Path,
    state_dir: Path,
    token: str,
    runner: ExternalRunner,
) -> tuple[Path | None, str | None]:
    """Generate a bridge in an isolated sibling directory using env-only auth."""
    state_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bridge-stage-", dir=str(state_dir)))
    command = [str(executable), "install-bridge", "photoshop", "--dest", str(staging), "--json"]
    env = os.environ.copy()
    env["ADOBEPY_TOKEN"] = token
    try:
        result = runner(command, env=env, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy bridge staging failed"

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if _contains_secret(stdout, token) or _contains_secret(stderr, token):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy emitted sensitive output; installation stopped"
    if result.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy bridge staging failed"
    if not (staging / "manifest.json").is_file():
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy did not produce a Photoshop manifest"
    return staging, None


def _file_receipts(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if path.name == "adobepy.config.js":
            files.append({"path": relative, "sensitive": True})
        else:
            files.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return files


def load_receipt(receipt_path: Path, expected_bridge_root: Path) -> dict[str, Any] | None:
    """Load only a receipt that is bound to this adapter-owned install root."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None
    if receipt.get("schema_version") != 1 or receipt.get("dcc_type") != "photoshop":
        return None
    try:
        recorded = Path(receipt["bridge_root"]).resolve()
    except (KeyError, OSError, TypeError):
        return None
    if recorded != expected_bridge_root.resolve():
        return None
    return receipt


def receipt_files_match(receipt: dict[str, Any], bridge_root: Path) -> bool:
    """Verify receipt-owned files without reading sensitive config contents."""
    items = receipt.get("files")
    if not isinstance(items, list) or not items:
        return False
    recorded_paths: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            return False
        relative = item.get("path")
        if not isinstance(relative, str):
            return False
        recorded_paths.add(relative)
        path = (bridge_root / relative).resolve()
        try:
            path.relative_to(bridge_root.resolve())
        except ValueError:
            return False
        if not path.is_file():
            return False
        expected = item.get("sha256")
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return False
    return "manifest.json" in recorded_paths


def remove_receipt_install(
    *,
    bridge_root: Path,
    receipt_path: Path,
) -> tuple[str, str | None]:
    """Remove only the bridge root named by a valid adapter receipt."""
    receipt = load_receipt(receipt_path, bridge_root)
    if receipt is None:
        return "failed", "A valid Photoshop install receipt is required"
    if bridge_root.exists():
        inspection = inspect_install_root(bridge_root)
        if inspection.get("requires_restart"):
            return "requires_restart", "A loaded native artifact requires Photoshop restart before uninstall"
        quarantine = bridge_root.with_name(f".{bridge_root.name}.uninstall-{os.getpid()}")
        try:
            os.replace(bridge_root, quarantine)
            shutil.rmtree(quarantine)
        except OSError:
            if quarantine.exists() and not bridge_root.exists():
                os.replace(quarantine, bridge_root)
            return "requires_restart", "Bridge files are locked; restart Photoshop and retry uninstall"
    try:
        receipt_path.unlink(missing_ok=True)
    except OSError:
        return "failed", "Bridge was removed but the receipt could not be deleted"
    return "ok", None


def commit_bridge(
    *,
    staging: Path,
    destination: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
    replacer: Callable[[Any, Any], Any] = os.replace,
) -> tuple[str, str | None]:
    """Atomically swap a staged bridge and roll back if receipt commit fails."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        inspection = inspect_install_root(destination)
        if inspection.get("requires_restart"):
            shutil.rmtree(staging, ignore_errors=True)
            return "requires_restart", "A loaded native artifact prevents bridge replacement"

    backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
    moved_previous = False
    try:
        if destination.exists():
            _replace_with_retry(replacer, destination, backup)
            moved_previous = True
        _replace_with_retry(replacer, staging, destination)
        receipt["files"] = _file_receipts(destination)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_temp = receipt_path.with_suffix(".tmp")
        receipt_temp.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        _replace_with_retry(replacer, receipt_temp, receipt_path)
    except OSError:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        if moved_previous and backup.exists():
            _replace_with_retry(replacer, backup, destination)
        shutil.rmtree(staging, ignore_errors=True)
        return "failed", "Bridge commit failed and the previous install was restored"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return "ok", None
