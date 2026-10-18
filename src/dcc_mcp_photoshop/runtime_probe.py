"""Runtime probes for the adobepy-backed Photoshop adapter."""

from __future__ import annotations

import json
import math
import os
import socket
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 1_048_576
_MAX_SESSIONS = 1_024


def _bounded_timeout(value: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.05 <= normalized <= 30.0:
        return None
    return normalized


def _safe_broker_base(value: str) -> str | None:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except (TypeError, ValueError):
        return None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port not in range(1, 65_536)
    ):
        return None
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{port}"


def _classified_failure(error_type: str) -> dict:
    return {"ok": False, "sessions": 0, "error_type": error_type}


def _request_json(request: Request, timeout: float):
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        return None, "unauthorized" if exc.code in {401, 403} else "http_error"
    except (TimeoutError, socket.timeout):
        return None, "timeout"
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return None, "timeout"
        return None, "connection_refused"
    except OSError:
        return None, "connection_failed"
    if len(raw) > _MAX_RESPONSE_BYTES:
        return None, "unbounded_payload"
    try:
        return json.loads(raw.decode("utf-8")), None
    except (json.JSONDecodeError, UnicodeError):
        return None, "invalid_json"


def _broker_identity(base: str, headers: dict, timeout: float) -> dict | None:
    """Best-effort fetch of the broker's own authenticated identity.

    ``GET /v1/broker-identity`` requires the broker token but no live host/bridge
    session, so it works the moment the broker is listening. The result feeds
    install verification, not liveness: a failure here leaves ``identity``
    ``None`` and never flips ``ok``, so a pre-session watchdog keeps reporting
    liveness while ``verify`` later fails closed with ``invalid_identity``.
    """
    payload, error_type = _request_json(
        Request(f"{base}/v1/broker-identity", headers=headers, method="GET"),
        timeout,
    )
    if error_type or not isinstance(payload, dict):
        return None
    # Map the broker wire identity (camelCase) to the adapter's snake_case shape.
    identity = {
        "pid": payload.get("pid"),
        "version": payload.get("runtimeVersion"),
        "executable": payload.get("executablePath"),
        "process_start_identity": payload.get("processStartIdentity"),
        "instance_id": payload.get("instanceId"),
    }
    if any(value is None for value in identity.values()):
        return None
    return identity


def _identity_field(source: object, snake: str, camel: str) -> object | None:
    """Read one identity field from a frozen dataclass or a wire mapping."""
    if source is None:
        return None
    if hasattr(source, snake):
        return getattr(source, snake)
    if isinstance(source, Mapping):
        if camel in source:
            return source[camel]
        if snake in source:
            return source[snake]
    return None


def _runtime_identity_to_mapping(runtime_identity: object, broker_url: str) -> dict | None:
    """Flatten an SDK ``RuntimeIdentityAttestation`` into the adapter's dict.

    The adobepy SDK returns a frozen dataclass exposing ``.host``/``.bridge``
    and ``to_wire()``; older or mocked surfaces may hand back a plain wire
    mapping. Both are accepted, but the required host/bridge sub-identities are
    not optional: without them the caller treats identity as absent and fails
    closed.
    """
    if runtime_identity is None:
        return None
    host = _identity_field(runtime_identity, "host", "host")
    bridge = _identity_field(runtime_identity, "bridge", "bridge")
    if host is None or bridge is None:
        return None
    return {
        "host": "photoshop",
        "host_pid": _identity_field(host, "pid", "pid"),
        "process_start_identity": _identity_field(host, "process_start_identity", "processStartIdentity"),
        "process_executable": _identity_field(host, "executable_path", "executablePath"),
        "host_version": _identity_field(host, "host_version", "hostVersion"),
        "profile_id": _identity_field(host, "profile_id", "profileId"),
        "target": _identity_field(bridge, "target", "target"),
        "bridge_kind": _identity_field(bridge, "bridge_kind", "bridgeKind"),
        "bridge_version": _identity_field(bridge, "bridge_version", "bridgeVersion"),
        "instance_id": _identity_field(bridge, "instance_id", "instanceId"),
        "plugin_root": _identity_field(bridge, "installed_plugin_root", "installedPluginRoot"),
        "plugin_module_origin": _identity_field(bridge, "module_origin", "moduleOrigin"),
        "connected_at_epoch_ms": _identity_field(bridge, "connected_at_epoch_ms", "connectedAtEpochMs"),
        "broker_url": broker_url,
    }


def probe_broker(broker_url: str, timeout: float) -> dict:
    """Return the broker health payload or a structured failure."""
    bounded_timeout = _bounded_timeout(timeout)
    base = _safe_broker_base(broker_url)
    if bounded_timeout is None or base is None:
        return _classified_failure("invalid_configuration")
    payload, error_type = _request_json(
        Request(f"{base}/health", method="GET"),
        bounded_timeout,
    )
    if error_type:
        return _classified_failure(error_type)
    if not isinstance(payload, dict):
        return _classified_failure("invalid_payload")
    try:
        sessions = int(payload.get("sessions"))
    except (TypeError, ValueError):
        return _classified_failure("invalid_payload")
    if (
        isinstance(payload.get("sessions"), bool)
        or sessions not in range(_MAX_SESSIONS + 1)
        or payload.get("status") != "ok"
        or payload.get("protocol") != "jsonrpc-2.0"
    ):
        return _classified_failure("invalid_payload")
    headers = {}
    token = os.environ.get("ADOBEPY_TOKEN", "")
    if token:
        headers["x-adobepy-token"] = token
    capabilities, error_type = _request_json(
        Request(f"{base}/v1/capabilities", headers=headers, method="GET"),
        bounded_timeout,
    )
    if error_type:
        return _classified_failure(error_type)
    if not isinstance(capabilities, list) or len(capabilities) != sessions:
        return _classified_failure("invalid_payload")
    if any(not isinstance(item, dict) for item in capabilities):
        return _classified_failure("invalid_payload")
    return {
        "ok": True,
        "sessions": sessions,
        "status": "ok",
        "protocol": "jsonrpc-2.0",
        "broker_url": base,
        "capabilities": capabilities,
        "identity": _broker_identity(base, headers, bounded_timeout),
    }


def probe_photoshop(broker_url: str, timeout: float) -> dict:
    """Execute a real host call through the broker."""
    bounded_timeout = _bounded_timeout(timeout)
    base = _safe_broker_base(broker_url)
    if bounded_timeout is None or base is None:
        return {"ok": False, "error_type": "invalid_configuration"}
    try:
        from adobe.photoshop import Photoshop  # noqa: PLC0415

        app = Photoshop(
            broker_url=base,
            token=os.environ.get("ADOBEPY_TOKEN"),
            target=os.environ.get("ADOBEPY_TARGET"),
            timeout=bounded_timeout,
        )
        version = app.version
        runtime_identity = getattr(app, "runtime_identity", None)
        if callable(runtime_identity):
            runtime_identity = runtime_identity()
    except TimeoutError:
        return {"ok": False, "error_type": "timeout"}
    except (OSError, ConnectionError):
        return {"ok": False, "error_type": "connection_failed"}
    except Exception as exc:  # noqa: BLE001 - third-party facade has typed subclasses at runtime
        name = type(exc).__name__.lower()
        if "auth" in name or "unauthor" in name:
            error_type = "unauthorized"
        elif "timeout" in name:
            error_type = "timeout"
        elif "json" in name or "parse" in name:
            error_type = "invalid_json"
        else:
            error_type = "host_rpc_failed"
        return {"ok": False, "error_type": error_type}
    if not isinstance(version, str) or not version:
        return {"ok": False, "error_type": "invalid_payload"}
    return {
        "ok": True,
        "version": version,
        "target": os.environ.get("ADOBEPY_TARGET", "default"),
        "broker_url": base,
        "identity": _runtime_identity_to_mapping(runtime_identity, base),
    }


def endpoint_host_port(url: str) -> tuple[str, int]:
    """Extract a TCP target from an HTTP endpoint."""
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"Invalid endpoint URL: {url}")
    return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
