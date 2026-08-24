"""Verify-to-usable checks for the installed Photoshop bridge."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from dcc_mcp_photoshop.install_contract import (
    INSTALL_SOP_SCHEMA_ID,
    INSTALL_SOP_SCHEMA_SHA256,
    INSTALL_SOP_SCHEMA_SIZE,
    version_tuple,
)
from dcc_mcp_photoshop.runtime_probe import probe_broker, probe_photoshop

Probe = Callable[[str, float], Dict[str, Any]]
PythonProbe = Callable[[str, float], Dict[str, Any]]
ProcessProbe = Callable[[int], Dict[str, Any]]


def _same_path(left: Any, right: Any) -> bool:
    try:
        left_text = os.fspath(left)
        right_text = os.fspath(right)
    except TypeError:
        return False
    if not _bounded_text(left_text, 4_096) or not _bounded_text(right_text, 4_096):
        return False
    try:
        return os.path.normcase(str(Path(left_text).resolve())) == os.path.normcase(str(Path(right_text).resolve()))
    except (OSError, TypeError, ValueError):
        return False


def _bounded_text(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and value == value.strip()
        and not any(ord(character) < 32 for character in value)
    )


def _process_executable_path(pid: int) -> Path | None:
    if pid <= 0:
        return None
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32_768)
            length = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                return None
            return Path(buffer.value).resolve()
        finally:
            kernel32.CloseHandle(handle)
    if sys.platform == "darwin":
        import ctypes  # noqa: PLC0415

        buffer = ctypes.create_string_buffer(4096)
        try:
            libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
            length = int(libproc.proc_pidpath(int(pid), buffer, len(buffer)))
        except (OSError, AttributeError):
            return None
        return Path(buffer.value.decode("utf-8")).resolve() if length > 0 else None
    try:
        return Path(f"/proc/{pid}/exe").resolve(strict=True)
    except OSError:
        return None


def _process_start_identity(pid: int) -> str | None:
    if pid <= 0:
        return None
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
            return f"windows-filetime:{value}"
        finally:
            kernel32.CloseHandle(handle)
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "lstart="],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = result.stdout.strip()
        return f"darwin-lstart:{value}" if result.returncode == 0 and value else None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        closing = stat.rfind(") ")
        start_ticks = stat[closing + 2 :].split()[19]
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except (IndexError, OSError, ValueError):
        return None
    return f"linux:{boot_id}:{start_ticks}"


def observe_process_identity(pid: int) -> dict[str, Any]:
    """Resolve a PID independently of broker-controlled metadata."""
    path = _process_executable_path(pid)
    start_identity = _process_start_identity(pid)
    if path is None or start_identity is None:
        return {"ok": False}
    return {
        "ok": True,
        "executable": str(path),
        "process_start_identity": start_identity,
    }


def _failure(stage: str, reason: str, error_type: str) -> dict[str, Any]:
    return {
        "directly_usable": False,
        "failure_stage": stage,
        "failure_reason": reason,
        "error_type": error_type,
    }


def probe_target_import(executable: str, timeout: float) -> dict[str, Any]:
    """Prove target imports belong to their selected distributions."""
    env = os.environ.copy()
    for name in ("ADOBEPY_TOKEN", "ADOBE_TOKEN"):
        env.pop(name, None)
    code = r"""
import importlib.metadata as metadata
import importlib.resources as resources
import hashlib
import json
import pathlib
import sys
import urllib.parse
import urllib.request

import adobe.photoshop
import dcc_mcp_core
import dcc_mcp_photoshop


def describe_core_schema():
    filename = "adapter-install-sop-v1.schema.json"
    contents = resources.read_binary("dcc_mcp_core.schemas", filename)
    schema = json.loads(contents.decode("utf-8"))
    distribution = metadata.distribution("dcc-mcp-core")
    record_path = "dcc_mcp_core/schemas/" + filename
    return {
        "id": schema.get("$id"),
        "size": len(contents),
        "sha256": hashlib.sha256(contents).hexdigest(),
        "record_owned": any(
            str(item).replace("\\", "/") == record_path
            for item in tuple(distribution.files or ())
        ),
    }


def describe(distribution_name, package_name, module):
    distribution = metadata.distribution(distribution_name)
    module_path = pathlib.Path(module.__file__).resolve()
    record_paths = {
        pathlib.Path(distribution.locate_file(item)).resolve()
        for item in tuple(distribution.files or ())
    }
    record_owned = module_path in record_paths
    editable_root = None
    try:
        raw = distribution.read_text("direct_url.json")
        direct_url = json.loads(raw) if raw else None
        url = direct_url.get("url") if isinstance(direct_url, dict) else None
        editable = (
            direct_url.get("dir_info", {}).get("editable") is True
            if isinstance(direct_url, dict)
            else False
        )
        parsed = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        if editable and parsed is not None and parsed.scheme == "file" and not parsed.query and not parsed.fragment:
            editable_root = pathlib.Path(
                urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
            ).resolve()
    except Exception:
        editable_root = None
    editable_owned = bool(
        editable_root
        and module_path
        in {
            editable_root / "src" / pathlib.Path(*package_name.split(".")) / "__init__.py",
            editable_root / pathlib.Path(*package_name.split(".")) / "__init__.py",
        }
    )
    return {
        "distribution": distribution_name,
        "version": distribution.version,
        "module_path": str(module_path),
        "owned": record_owned or editable_owned,
    }


print(json.dumps({
    "python_executable": sys.executable,
    "modules": {
        "adapter": describe("dcc-mcp-photoshop", "dcc_mcp_photoshop", dcc_mcp_photoshop),
        "core": describe("dcc-mcp-core", "dcc_mcp_core", dcc_mcp_core),
        "adobepy": describe("adobepy", "adobe.photoshop", adobe.photoshop),
    },
    "core_schema": describe_core_schema(),
}))
""".strip()
    try:
        result = subprocess.run(
            [executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except OSError:
        return {"ok": False, "error_type": "invalid_executable"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_type": "timeout"}
    except subprocess.SubprocessError:
        return {"ok": False, "error_type": "probe_failed"}
    if result.returncode != 0:
        return {"ok": False, "error_type": "import_failed"}
    stdout = result.stdout or ""
    if len(stdout.encode("utf-8", errors="replace")) > 262_144:
        return {"ok": False, "error_type": "unbounded_output"}
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeError):
        return {"ok": False, "error_type": "invalid_json"}
    if not isinstance(payload, dict) or not isinstance(payload.get("modules"), dict):
        return {"ok": False, "error_type": "invalid_payload"}
    core_schema = payload.get("core_schema")
    if (
        not isinstance(core_schema, dict)
        or core_schema.get("id") != INSTALL_SOP_SCHEMA_ID
        or core_schema.get("size") != INSTALL_SOP_SCHEMA_SIZE
        or core_schema.get("sha256") != INSTALL_SOP_SCHEMA_SHA256
        or core_schema.get("record_owned") is not True
    ):
        return {"ok": False, "error_type": "core_schema_mismatch"}
    try:
        reported_python = Path(payload["python_executable"]).resolve()
        selected_python = Path(executable).resolve()
    except (KeyError, OSError, TypeError):
        return {"ok": False, "error_type": "invalid_payload"}
    if reported_python != selected_python:
        return {"ok": False, "error_type": "python_identity_mismatch"}
    expected = {
        "adapter": "dcc-mcp-photoshop",
        "core": "dcc-mcp-core",
        "adobepy": "adobepy",
    }
    for key, distribution in expected.items():
        module = payload["modules"].get(key)
        if not isinstance(module, dict):
            return {"ok": False, "error_type": "invalid_payload"}
        if module.get("distribution") != distribution or module.get("owned") is not True:
            return {"ok": False, "error_type": "untrusted_module_origin"}
        if not version_tuple(module.get("version")):
            return {"ok": False, "error_type": "invalid_version"}
        try:
            module_path_value = module["module_path"]
            if not _bounded_text(module_path_value, 4_096):
                raise TypeError
            module_path = Path(module_path_value)
        except (KeyError, TypeError):
            return {"ok": False, "error_type": "invalid_payload"}
        if not module_path.is_file():
            return {"ok": False, "error_type": "untrusted_module_origin"}
    return {
        "ok": True,
        "python_executable": str(reported_python),
        "modules": payload["modules"],
        "core_schema": core_schema,
    }


def verify_photoshop_rpc(
    broker_url: str,
    *,
    python_executable: str,
    expected_host: Mapping[str, Any] | None = None,
    expected_bridge: Mapping[str, Any] | None = None,
    expected_bridge_root: str | Path | None = None,
    expected_python: Mapping[str, Any] | None = None,
    python_probe: PythonProbe = probe_target_import,
    broker_probe: Probe = probe_broker,
    photoshop_probe: Probe = probe_photoshop,
    process_probe: ProcessProbe = observe_process_identity,
) -> dict[str, Any]:
    """Require one receipt-bound UXP session and independently bound host PID."""
    target_import = python_probe(python_executable, 10.0)
    if not target_import.get("ok"):
        return _failure(
            "target_import",
            "The selected Python cannot import trusted adapter, Core, and adobepy modules",
            str(target_import.get("error_type", "import_failed")),
        )
    modules = target_import.get("modules")
    if (
        not isinstance(modules, dict)
        or set(modules) != {"adapter", "core", "adobepy"}
        or not _same_path(target_import.get("python_executable"), python_executable)
    ):
        return _failure(
            "target_import_identity",
            "The selected Python omitted its trusted distribution identity",
            "invalid_identity",
        )
    if expected_python is not None:
        expected_modules = expected_python.get("modules")
        if not isinstance(expected_modules, dict) or modules != expected_modules:
            return _failure(
                "target_import_identity",
                "Target module origins differ from the install receipt",
                "identity_mismatch",
            )

    broker = broker_probe(broker_url, 5.0)
    if not broker.get("ok"):
        return _failure(
            "broker_health",
            "The adobepy broker health probe failed",
            str(broker.get("error_type", "broker_unavailable")),
        )
    broker_identity = broker.get("identity")
    if not isinstance(broker_identity, dict):
        return _failure(
            "broker_identity",
            "The broker omitted its executable and process identity",
            "invalid_identity",
        )
    try:
        broker_pid = int(broker_identity["pid"])
    except (KeyError, TypeError, ValueError):
        return _failure(
            "broker_identity",
            "The broker omitted a bounded process id",
            "invalid_identity",
        )
    expected_broker_path = (
        expected_bridge.get("installer") if expected_bridge is not None else broker_identity.get("executable")
    )
    expected_broker_version = (
        expected_bridge.get("installer_version") if expected_bridge is not None else broker_identity.get("version")
    )
    if (
        broker_pid <= 0
        or broker_pid > 2_147_483_647
        or not version_tuple(broker_identity.get("version"))
        or broker_identity.get("version") != expected_broker_version
        or not _bounded_text(broker_identity.get("executable"), 4_096)
        or not _same_path(broker_identity.get("executable"), expected_broker_path)
        or not _bounded_text(broker_identity.get("process_start_identity"), 256)
        or not _bounded_text(broker_identity.get("instance_id"), 256)
    ):
        return _failure(
            "broker_identity",
            "The broker process differs from the selected adobepy runtime",
            "identity_mismatch",
        )
    broker_before = process_probe(broker_pid)
    broker_after = process_probe(broker_pid)
    if (
        broker_before.get("ok") is not True
        or broker_after.get("ok") is not True
        or broker_before != broker_after
        or not _same_path(broker_before.get("executable"), expected_broker_path)
        or broker_before.get("process_start_identity") != broker_identity["process_start_identity"]
    ):
        return _failure(
            "broker_identity",
            "The adobepy broker PID/start/path identity is stale or foreign",
            "process_identity_mismatch",
        )
    target = os.environ.get("ADOBEPY_TARGET", "default")
    if not isinstance(target, str) or re.fullmatch(r"[A-Za-z0-9._-]{1,128}", target) is None:
        return _failure(
            "broker_identity",
            "The selected adobepy target is not a bounded canonical identifier",
            "invalid_configuration",
        )
    capabilities = broker.get("capabilities")
    if not isinstance(capabilities, list):
        return _failure(
            "broker_identity",
            "The broker omitted authenticated capability sessions",
            "invalid_identity",
        )
    matches = []
    for session in capabilities:
        if not isinstance(session, dict):
            continue
        capability = session.get("capabilities")
        if (
            isinstance(capability, dict)
            and session.get("target") == target
            and capability.get("host") == "photoshop"
            and capability.get("bridgeKind") == "uxp"
        ):
            matches.append(session)
    if len(matches) != 1:
        return _failure(
            "broker_identity",
            "Exactly one authenticated Photoshop UXP target must be connected",
            "ambiguous_or_missing_session",
        )
    session = matches[0]
    capability = session["capabilities"]
    bridge_version = capability.get("bridgeVersion")
    session_host_version = capability.get("hostVersion")
    connected_at = session.get("connectedAtEpochMs")
    if (
        not version_tuple(bridge_version)
        or not version_tuple(session_host_version)
        or isinstance(connected_at, bool)
        or not isinstance(connected_at, int)
        or connected_at <= 0
        or connected_at > 9_223_372_036_854_775_807
    ):
        return _failure(
            "broker_identity",
            "The Photoshop UXP session contains noncanonical identity fields",
            "invalid_identity",
        )

    photoshop = photoshop_probe(broker_url, 5.0)
    if not photoshop.get("ok"):
        return _failure(
            "photoshop_rpc",
            "A real typed Photoshop RPC failed",
            str(photoshop.get("error_type", "host_rpc_failed")),
        )
    identity = photoshop.get("identity")
    if not isinstance(identity, dict):
        return _failure(
            "photoshop_identity",
            "The typed Photoshop RPC omitted runtime identity attestation",
            "invalid_identity",
        )
    try:
        host_pid = int(identity["host_pid"])
    except (KeyError, TypeError, ValueError):
        return _failure(
            "photoshop_identity",
            "The typed Photoshop RPC omitted a bounded host PID",
            "invalid_identity",
        )
    string_fields = {
        "host": "photoshop",
        "bridge_kind": "uxp",
        "target": target,
        "host_version": session_host_version,
        "bridge_version": bridge_version,
        "process_start_identity": identity.get("process_start_identity"),
        "process_executable": identity.get("process_executable"),
        "instance_id": identity.get("instance_id"),
        "profile_id": identity.get("profile_id"),
        "plugin_root": identity.get("plugin_root"),
        "plugin_module_origin": identity.get("plugin_module_origin"),
        "broker_url": broker.get("broker_url"),
    }
    for key, expected in string_fields.items():
        actual = identity.get(key)
        if not _bounded_text(actual, 4_096) or (isinstance(expected, str) and actual != expected):
            return _failure(
                "photoshop_identity",
                "The typed Photoshop RPC identity does not match its broker session",
                "identity_mismatch",
            )
    if host_pid <= 0 or host_pid > 2_147_483_647:
        return _failure(
            "photoshop_identity",
            "The typed Photoshop RPC reported an invalid host PID",
            "invalid_identity",
        )
    if photoshop.get("version") != session_host_version:
        return _failure(
            "photoshop_identity",
            "The typed Photoshop version differs from its UXP session",
            "identity_mismatch",
        )
    if identity.get("connected_at_epoch_ms") != connected_at:
        return _failure(
            "photoshop_identity",
            "The typed Photoshop RPC belongs to a stale broker connection",
            "stale_session",
        )
    host_executable = expected_host.get("executable") if expected_host else identity["process_executable"]
    if not _same_path(identity["process_executable"], host_executable):
        return _failure(
            "photoshop_identity",
            "The ready Photoshop process differs from the selected executable",
            "wrong_host",
        )
    bridge_root = expected_bridge_root or identity["plugin_root"]
    if not _same_path(identity["plugin_root"], bridge_root):
        return _failure(
            "photoshop_identity",
            "The ready UXP bridge differs from the receipted installation",
            "wrong_plugin_origin",
        )
    try:
        module_origin = Path(identity["plugin_module_origin"]).resolve()
        module_origin.relative_to(Path(bridge_root).resolve())
    except (OSError, TypeError, ValueError):
        return _failure(
            "photoshop_identity",
            "The ready UXP module origin is outside the receipted installation",
            "wrong_plugin_origin",
        )
    if not module_origin.is_file():
        return _failure(
            "photoshop_identity",
            "The ready UXP module origin is missing",
            "wrong_plugin_origin",
        )
    before = process_probe(host_pid)
    after = process_probe(host_pid)
    if (
        before.get("ok") is not True
        or after.get("ok") is not True
        or before != after
        or not _same_path(before.get("executable"), host_executable)
        or before.get("process_start_identity") != identity["process_start_identity"]
    ):
        return _failure(
            "photoshop_identity",
            "The Photoshop PID/start/path identity is stale or foreign",
            "process_identity_mismatch",
        )
    return {
        "directly_usable": True,
        "failure_stage": None,
        "failure_reason": None,
        "error_type": None,
    }
