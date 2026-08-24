"""Filesystem and external-process ownership for the Photoshop installer."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable

from dcc_mcp_core.install_lifecycle import inspect_install_root

from dcc_mcp_photoshop.install_discovery import path_uses_link

ExternalRunner = Callable[..., subprocess.CompletedProcess]


def _stream_sha256(path: Path, expected_size: int) -> str | None:
    try:
        if expected_size <= 0 or path.stat().st_size != expected_size:
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


def _adobepy_identity_matches(executable: Path, expected: dict[str, Any]) -> bool:
    try:
        expected_path = Path(expected["executable"]).resolve(strict=True)
        selected_path = executable.resolve(strict=True)
        manifest_path = Path(expected["manifest_path"]).resolve(strict=True)
        executable_bytes = int(expected["bytes"])
        manifest_bytes = int(expected["manifest_bytes"])
        executable_sha256 = expected["sha256"]
        manifest_sha256 = expected["manifest_sha256"]
    except (KeyError, OSError, TypeError, ValueError):
        return False
    if (
        expected.get("provenance") != "official_checksum_release"
        or os.path.normcase(str(expected_path)) != os.path.normcase(str(selected_path))
        or manifest_path != selected_path.parent.parent / "package-manifest.json"
        or path_uses_link(executable)
        or path_uses_link(manifest_path)
        or not isinstance(executable_sha256, str)
        or not isinstance(manifest_sha256, str)
        or len(executable_sha256) != 64
        or len(manifest_sha256) != 64
    ):
        return False
    try:
        before = selected_path.stat()
        manifest_before = manifest_path.stat()
    except OSError:
        return False
    if _stream_sha256(selected_path, executable_bytes) != executable_sha256:
        return False
    if _stream_sha256(manifest_path, manifest_bytes) != manifest_sha256:
        return False
    try:
        after = selected_path.stat()
        manifest_after = manifest_path.stat()
    except OSError:
        return False
    return (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) and (
        manifest_before.st_dev,
        manifest_before.st_ino,
        manifest_before.st_size,
        manifest_before.st_mtime_ns,
    ) == (
        manifest_after.st_dev,
        manifest_after.st_ino,
        manifest_after.st_size,
        manifest_after.st_mtime_ns,
    )


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
    expected_identity: dict[str, Any],
    state_dir: Path,
    token: str,
    runner: ExternalRunner,
) -> tuple[Path | None, str | None]:
    """Generate a bridge in an isolated sibling directory using env-only auth."""
    if not _adobepy_identity_matches(executable, expected_identity):
        return None, "adobepy CLI identity changed before bridge staging"
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
    if len(stdout.encode("utf-8", errors="replace")) > 65_536 or len(stderr.encode("utf-8", errors="replace")) > 65_536:
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy emitted unbounded bridge staging output"
    if _contains_secret(stdout, token) or _contains_secret(stderr, token):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy emitted sensitive output; installation stopped"
    if result.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy bridge staging failed"
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeError):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy returned invalid bridge staging metadata"
    if not isinstance(payload, dict):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy returned untrusted bridge staging metadata"
    expected_config = staging / "adobepy.config.js"
    try:
        destination_matches = Path(payload["destination"]).resolve() == staging.resolve()
        config_matches = Path(payload["config"]).resolve() == expected_config.resolve()
    except (KeyError, OSError, TypeError):
        destination_matches = False
        config_matches = False
    if (
        payload.get("success") is not True
        or payload.get("host") != "photoshop"
        or payload.get("kind") != "uxp"
        or payload.get("token_configured") is not True
        or not destination_matches
        or not config_matches
        or not expected_config.is_file()
        or not (staging / "manifest.json").is_file()
    ):
        shutil.rmtree(staging, ignore_errors=True)
        return None, "adobepy returned untrusted bridge staging metadata"
    return staging, None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative(value: Any) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return Path(*pure.parts)


def _safe_symlink_target(link_path: str, target: Any) -> bool:
    """Accept only bounded relative links whose lexical target stays in the install root."""
    if not isinstance(target, str) or not target or len(target) > 4_096 or "\0" in target:
        return False
    if PurePosixPath(target).is_absolute() or PureWindowsPath(target).is_absolute():
        return False
    stack = list(PurePosixPath(link_path).parent.parts)
    for part in PurePosixPath(target.replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not stack:
                return False
            stack.pop()
        else:
            stack.append(part)
    return bool(stack)


def _owned_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not root.is_dir() or path_uses_link(root):
        raise OSError("Photoshop bridge root is redirected by a link or reparse point")
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    def visit(directory: Path, relative_parent: PurePosixPath) -> None:
        try:
            with os.scandir(directory) as scanner:
                children = sorted(scanner, key=lambda item: item.name)
        except OSError as exc:
            raise OSError("Photoshop bridge ownership scan failed") from exc
        for child in children:
            path = Path(child.path)
            relative_path = relative_parent / child.name
            relative = relative_path.as_posix()
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise OSError(f"Photoshop bridge entry changed during ownership scan: {relative}") from exc
            is_link = stat.S_ISLNK(metadata.st_mode)
            is_reparse = bool(getattr(metadata, "st_file_attributes", 0) & reparse_flag)
            if is_link:
                target = os.readlink(path)
                if not _safe_symlink_target(relative, target):
                    raise OSError(f"Unsafe bridge symlink target: {relative}")
                target_bytes = os.fsencode(target)
                entries.append(
                    {
                        "path": relative,
                        "type": "symlink",
                        "target": target,
                        "bytes": len(target_bytes),
                        "sha256": _sha256(target_bytes),
                    }
                )
            elif is_reparse:
                raise OSError(f"Unsupported bridge reparse point: {relative}")
            elif stat.S_ISDIR(metadata.st_mode):
                entries.append(
                    {
                        "path": relative,
                        "type": "directory",
                        "bytes": 0,
                        "sha256": _sha256(("directory\0" + relative).encode("utf-8")),
                    }
                )
                visit(path, relative_path)
            elif stat.S_ISREG(metadata.st_mode):
                contents = path.read_bytes()
                after = path.lstat()
                before_identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
                after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                if before_identity != after_identity or bool(getattr(after, "st_file_attributes", 0) & reparse_flag):
                    raise OSError(f"Photoshop bridge entry changed during ownership scan: {relative}")
                entry = {
                    "path": relative,
                    "type": "file",
                    "bytes": len(contents),
                    "sha256": _sha256(contents),
                }
                if path.name == "adobepy.config.js":
                    entry["sensitive"] = True
                entries.append(entry)
            else:
                raise OSError(f"Unsupported bridge entry type: {relative}")

    visit(root, PurePosixPath())
    return sorted(entries, key=lambda item: item["path"])


def _manifest_digest(entries: list[dict[str, Any]]) -> str:
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def _installation_id(receipt: dict[str, Any], bridge_root: Path) -> str:
    binding = {
        "receipt_version": receipt.get("receipt_version"),
        "schema_version": receipt.get("schema_version"),
        "dcc_type": receipt.get("dcc_type"),
        "adapter_version": receipt.get("adapter_version"),
        "core_version": receipt.get("core_version"),
        "host": receipt.get("host"),
        "python": receipt.get("python"),
        "bridge": receipt.get("bridge"),
        "bridge_root": str(bridge_root.resolve()),
    }
    encoded = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def load_receipt(receipt_path: Path, expected_bridge_root: Path) -> dict[str, Any] | None:
    """Load only a receipt that is bound to this adapter-owned install root."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None
    if (
        receipt.get("receipt_version") != 1
        or receipt.get("schema_version") != 1
        or receipt.get("dcc_type") != "photoshop"
    ):
        return None
    try:
        recorded = Path(receipt["bridge_root"]).resolve()
    except (KeyError, OSError, TypeError):
        return None
    if recorded != expected_bridge_root.resolve():
        return None
    expected_id = _installation_id(receipt, recorded)
    if receipt.get("installation_id") != expected_id:
        return None
    return receipt


def receipt_files_match(receipt: dict[str, Any], bridge_root: Path) -> bool:
    """Verify the exact typed closure owned by the install receipt."""
    items = receipt.get("owned_entries")
    if not isinstance(items, list) or not items:
        return False
    recorded_paths: set[Path] = set()
    for item in items:
        if not isinstance(item, dict):
            return False
        relative = _safe_relative(item.get("path"))
        if relative is None or relative in recorded_paths:
            return False
        recorded_paths.add(relative)
        if item.get("type") not in {"file", "directory", "symlink"}:
            return False
        if not isinstance(item.get("bytes"), int) or isinstance(item.get("bytes"), bool):
            return False
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            return False
    try:
        actual = _owned_entries(bridge_root)
    except OSError:
        return False
    if actual != items:
        return False
    return Path("manifest.json") in recorded_paths and receipt.get("manifest_sha256") == _manifest_digest(items)


def _write_bytes_atomic(
    path: Path,
    contents: bytes,
    replacer: Callable[[Any, Any], Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(contents)
        _replace_with_retry(replacer, temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass
class BridgeCommitTransaction:
    """Keep the prior bridge and receipt until bound verification finishes."""

    destination: Path
    backup: Path
    receipt_path: Path
    old_receipt: bytes | None
    replacer: Callable[[Any, Any], Any]
    moved_previous: bool = False
    replacement_moved: bool = False
    closed: bool = False

    def rollback(self) -> None:
        if self.closed:
            return
        failed = self.destination.with_name(f".{self.destination.name}.failed-{uuid.uuid4().hex}")
        try:
            if self.replacement_moved and self.destination.exists():
                _replace_with_retry(self.replacer, self.destination, failed)
            if self.moved_previous:
                if not self.backup.exists():
                    raise OSError("previous Photoshop bridge backup is missing")
                _replace_with_retry(self.replacer, self.backup, self.destination)
            if self.old_receipt is None:
                self.receipt_path.unlink(missing_ok=True)
            else:
                _write_bytes_atomic(self.receipt_path, self.old_receipt, self.replacer)
            if self.moved_previous:
                restored = load_receipt(self.receipt_path, self.destination)
                if restored is None or not receipt_files_match(restored, self.destination):
                    raise OSError("previous Photoshop bridge did not validate after rollback")
            self.closed = True
        finally:
            if failed.exists():
                shutil.rmtree(failed, ignore_errors=True)
            if self.closed and self.backup.exists():
                shutil.rmtree(self.backup, ignore_errors=True)

    def finalize(self) -> None:
        if self.closed:
            return
        if self.backup.exists():
            shutil.rmtree(self.backup)
        self.closed = True


def remove_receipt_install(
    *,
    bridge_root: Path,
    receipt_path: Path,
) -> tuple[str, str | None]:
    """Atomically remove only the complete bridge named by a valid receipt."""
    receipt = load_receipt(receipt_path, bridge_root)
    if receipt is None:
        return "failed", "A valid Photoshop install receipt is required"
    if not bridge_root.exists() or not receipt_files_match(receipt, bridge_root):
        return "failed", "The Photoshop bridge no longer matches its install receipt"

    inspection = inspect_install_root(bridge_root)
    if inspection.get("requires_restart"):
        return "requires_restart", "A loaded native artifact requires Photoshop restart before uninstall"

    recovery = bridge_root.with_name(f".{bridge_root.name}.recovery-{uuid.uuid4().hex}")
    quarantine = bridge_root.with_name(f".{bridge_root.name}.uninstall-{uuid.uuid4().hex}")
    receipt_bytes = receipt_path.read_bytes()

    def cleanup(path: Path) -> bool:
        try:
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.exists():
                shutil.rmtree(path)
        except OSError:
            return False
        return not path.exists()

    def restore() -> bool:
        try:
            cleanup(bridge_root)
            shutil.copytree(recovery, bridge_root, symlinks=True, copy_function=shutil.copy2)
            _write_bytes_atomic(receipt_path, receipt_bytes, os.replace)
            restored = load_receipt(receipt_path, bridge_root)
            if restored is None or not receipt_files_match(restored, bridge_root):
                raise OSError("Photoshop uninstall recovery did not validate")
        except OSError:
            return False
        cleanup(quarantine)
        cleanup(recovery)
        return True

    bridge_moved = False
    try:
        shutil.copytree(bridge_root, recovery, symlinks=True, copy_function=shutil.copy2)
        if not receipt_files_match(receipt, recovery):
            raise OSError("Photoshop uninstall recovery snapshot did not validate")
        os.replace(bridge_root, quarantine)
        bridge_moved = True
        shutil.rmtree(quarantine)
    except OSError:
        if not bridge_moved:
            cleanup(recovery)
            return "failed", "Photoshop uninstall staging failed; no bridge files were removed"
        if not restore():
            return "failed", "Photoshop bridge removal failed and recovery requires operator action"
        return "requires_restart", "Bridge files are locked; restart Photoshop and retry uninstall"

    try:
        receipt_path.unlink()
    except OSError:
        if not restore():
            return "failed", "Photoshop receipt removal failed and recovery requires operator action"
        return "failed", "Photoshop receipt removal failed; the bridge was restored"

    if not cleanup(recovery):
        if restore():
            return "requires_restart", "Uninstall cleanup failed; the Photoshop bridge was restored"
        return "failed", "Uninstall cleanup failed and recovery requires operator action"
    return "ok", None


def begin_bridge_commit(
    *,
    staging: Path,
    destination: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
    replacer: Callable[[Any, Any], Any] = os.replace,
    expected_previous_receipt: bytes | None = None,
    require_fresh_destination: bool = False,
) -> tuple[str, str | None, BridgeCommitTransaction | None]:
    """Swap in one bridge while retaining rollback state through verification."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if expected_previous_receipt is not None:
        try:
            current_receipt = receipt_path.read_bytes()
        except OSError:
            current_receipt = None
        previous = load_receipt(receipt_path, destination)
        if (
            current_receipt != expected_previous_receipt
            or previous is None
            or not receipt_files_match(previous, destination)
        ):
            shutil.rmtree(staging, ignore_errors=True)
            return "failed", "The previous Photoshop install changed before replacement", None
    elif require_fresh_destination and (destination.exists() or receipt_path.exists()):
        shutil.rmtree(staging, ignore_errors=True)
        return "failed", "Unowned Photoshop bridge state appeared before installation", None
    if destination.exists():
        inspection = inspect_install_root(destination)
        if inspection.get("requires_restart"):
            shutil.rmtree(staging, ignore_errors=True)
            return (
                "requires_restart",
                "A loaded native artifact prevents bridge replacement",
                None,
            )

    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    old_receipt = expected_previous_receipt
    if old_receipt is None and receipt_path.is_file():
        old_receipt = receipt_path.read_bytes()
    transaction = BridgeCommitTransaction(
        destination=destination,
        backup=backup,
        receipt_path=receipt_path,
        old_receipt=old_receipt,
        replacer=replacer,
    )
    try:
        if destination.exists():
            _replace_with_retry(replacer, destination, backup)
            transaction.moved_previous = True
        _replace_with_retry(replacer, staging, destination)
        transaction.replacement_moved = True
        receipt["receipt_version"] = 1
        receipt["installation_id"] = _installation_id(receipt, destination)
        receipt["owned_entries"] = _owned_entries(destination)
        receipt["manifest_sha256"] = _manifest_digest(receipt["owned_entries"])
        _write_bytes_atomic(
            receipt_path,
            (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            replacer,
        )
        committed = load_receipt(receipt_path, destination)
        if committed is None or not receipt_files_match(committed, destination):
            raise OSError("Photoshop bridge receipt did not validate after commit")
    except OSError:
        try:
            transaction.rollback()
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
            return "failed", "Bridge commit failed and rollback could not be verified", None
        shutil.rmtree(staging, ignore_errors=True)
        return "failed", "Bridge commit failed and the previous install was restored", None
    return "ok", None, transaction


def commit_bridge(
    *,
    staging: Path,
    destination: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
    replacer: Callable[[Any, Any], Any] = os.replace,
) -> tuple[str, str | None]:
    """Compatibility wrapper for callers that do not need deferred verification."""
    status, error, transaction = begin_bridge_commit(
        staging=staging,
        destination=destination,
        receipt_path=receipt_path,
        receipt=receipt,
        replacer=replacer,
    )
    if transaction is not None:
        try:
            transaction.finalize()
        except OSError:
            return "requires_restart", "Verified bridge backup cleanup requires a Photoshop restart"
    return status, error
