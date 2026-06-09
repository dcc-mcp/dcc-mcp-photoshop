"""Photoshop UXP WebSocket bridge protocol v0 — message builders and validators.

Defines the wire format for Python ↔ UXP communication.
See docs/bridge-protocol.md for the full specification.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

# ── Protocol identity ──────────────────────────────────────────────────────

PROTOCOL_NAME = "photoshop-bridge"
PROTOCOL_VERSION = "0.1.0"
PROTOCOL_TAG = f"{PROTOCOL_NAME}/{PROTOCOL_VERSION}"

# ── Message types ──────────────────────────────────────────────────────────

TYPE_HELLO = "hello"
TYPE_HELLO_ACK = "hello_ack"
TYPE_DISCONNECTED = "disconnected"
TYPE_PROGRESS = "progress"

# ── Standard JSON-RPC 2.0 error codes ──────────────────────────────────────

RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603

# ── Photoshop bridge custom error codes ────────────────────────────────────

CUSTOM_ERR_NO_ACTIVE_DOC = -32001
CUSTOM_ERR_LAYER_NOT_FOUND = -32002
CUSTOM_ERR_UNSUPPORTED_FORMAT = -32003
CUSTOM_ERR_FILE_NOT_FOUND = -32004
CUSTOM_ERR_SCRIPT_ERROR = -32005
CUSTOM_ERR_TIMEOUT = -32006
CUSTOM_ERR_DISCONNECTED = -32007

# ── Error code → hint mapping ──────────────────────────────────────────────

_ERROR_HINTS: Dict[int, str] = {
    RPC_PARSE_ERROR: "The JSON payload could not be parsed. Check for malformed escape sequences or trailing commas.",
    RPC_INVALID_REQUEST: "The request must be a JSON object with 'jsonrpc', 'id', 'method', and 'params' fields.",
    RPC_METHOD_NOT_FOUND: "Use ps.describeApi to list available methods.",
    RPC_INVALID_PARAMS: "Check the method's required parameters and their types.",
    RPC_INTERNAL_ERROR: "An unexpected error occurred inside the Photoshop handler. Check the plugin log for details.",
    CUSTOM_ERR_NO_ACTIVE_DOC: "Open or create a document before calling document/layer methods.",
    CUSTOM_ERR_LAYER_NOT_FOUND: "Use ps.listLayers to see the current layer tree.",
    CUSTOM_ERR_UNSUPPORTED_FORMAT: "Supported formats: png, jpg, tiff, psd.",
    CUSTOM_ERR_FILE_NOT_FOUND: "Verify the path exists and Photoshop has permission to access it.",
    CUSTOM_ERR_SCRIPT_ERROR: "The JavaScript expression could not be evaluated. Check syntax and available APIs.",
    CUSTOM_ERR_TIMEOUT: "The operation took too long and was cancelled. Try a smaller operation or increase the timeout.",
    CUSTOM_ERR_DISCONNECTED: "The UXP plugin lost connection. It will auto-reconnect. Retry the call once reconnected.",
}

# ── Message builders ───────────────────────────────────────────────────────


def build_hello(client: str = "photoshop-uxp", reconnect: bool = False) -> Dict[str, Any]:
    msg: Dict[str, Any] = {
        "type": TYPE_HELLO,
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "client": client,
    }
    if reconnect:
        msg["reconnect"] = True
    return msg


def build_hello_ack() -> Dict[str, Any]:
    return {
        "type": TYPE_HELLO_ACK,
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
    }


def build_hello_ack_error(reason: str) -> Dict[str, Any]:
    return {
        "type": TYPE_HELLO_ACK,
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "compatible": False,
        "error": reason,
    }


def build_disconnected(reason: str = "Server stopped") -> Dict[str, Any]:
    return {
        "type": TYPE_DISCONNECTED,
        "reason": reason,
    }


def build_request(req_id: int, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


def build_success(req_id: int, result: Any) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def build_error(
    req_id: Optional[int],
    code: int,
    message: str,
    hint: Optional[str] = None,
    data: Any = None,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if hint is None:
        hint = _ERROR_HINTS.get(code)
    if hint:
        error["hint"] = hint
    if data is not None:
        error["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": error,
    }


def build_progress(
    req_id: int,
    current: int,
    total: int,
    message: str = "",
    stage: Optional[str] = None,
) -> Dict[str, Any]:
    progress: Dict[str, Any] = {"current": current, "total": total}
    if message:
        progress["message"] = message
    if stage:
        progress["stage"] = stage
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "type": TYPE_PROGRESS,
        "progress": progress,
    }


# ── Validators ─────────────────────────────────────────────────────────────


def is_hello(msg: Dict[str, Any]) -> bool:
    return msg.get("type") == TYPE_HELLO and msg.get("protocol") == PROTOCOL_NAME


def is_rpc_request(msg: Dict[str, Any]) -> bool:
    return (
        msg.get("jsonrpc") == "2.0"
        and isinstance(msg.get("id"), (int, float))
        and isinstance(msg.get("method"), str)
        and isinstance(msg.get("params"), dict)
    )


def is_rpc_response(msg: Dict[str, Any]) -> bool:
    if msg.get("jsonrpc") != "2.0":
        return False
    if not isinstance(msg.get("id"), (int, float)):
        return False
    return "result" in msg or "error" in msg


def is_progress(msg: Dict[str, Any]) -> bool:
    return (
        msg.get("jsonrpc") == "2.0"
        and msg.get("type") == TYPE_PROGRESS
        and isinstance(msg.get("id"), (int, float))
        and isinstance(msg.get("progress"), dict)
    )


def check_version(version: str) -> bool:
    try:
        parts = version.split(".")
        major = int(parts[0])
        return major == 0
    except (ValueError, IndexError):
        return False


def parse_message(raw: str) -> Optional[Dict[str, Any]]:
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return msg if isinstance(msg, dict) else None
