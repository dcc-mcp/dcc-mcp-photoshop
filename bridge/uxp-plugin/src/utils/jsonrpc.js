/**
 * JSON-RPC 2.0 helpers + Photoshop bridge protocol v0.
 *
 * See: https://www.jsonrpc.org/specification
 * See: docs/bridge-protocol.md
 */

"use strict";

// ── Protocol identity ────────────────────────────────────────────────────────

const PROTOCOL_NAME = "photoshop-bridge";
const PROTOCOL_VERSION = "0.1.0";

// ── Standard JSON-RPC 2.0 error codes ────────────────────────────────────────

const RPC_PARSE_ERROR = -32700;
const RPC_INVALID_REQUEST = -32600;
const RPC_METHOD_NOT_FOUND = -32601;
const RPC_INVALID_PARAMS = -32602;
const RPC_INTERNAL_ERROR = -32603;

// ── Photoshop bridge custom error codes ───────────────────────────────────────

const CUSTOM_ERR_NO_ACTIVE_DOC     = -32001;
const CUSTOM_ERR_LAYER_NOT_FOUND   = -32002;
const CUSTOM_ERR_UNSUPPORTED_FORMAT = -32003;
const CUSTOM_ERR_FILE_NOT_FOUND    = -32004;
const CUSTOM_ERR_SCRIPT_ERROR      = -32005;
const CUSTOM_ERR_TIMEOUT           = -32006;
const CUSTOM_ERR_DISCONNECTED      = -32007;

// ── Error code → hint mapping ─────────────────────────────────────────────────

const ERROR_HINTS = {};
ERROR_HINTS[RPC_PARSE_ERROR]         = "The JSON payload could not be parsed. Check for malformed escape sequences or trailing commas.";
ERROR_HINTS[RPC_INVALID_REQUEST]     = "The request must be a JSON object with 'jsonrpc', 'id', 'method', and 'params' fields.";
ERROR_HINTS[RPC_METHOD_NOT_FOUND]    = "Use ps.describeApi to list available methods.";
ERROR_HINTS[RPC_INVALID_PARAMS]      = "Check the method's required parameters and their types.";
ERROR_HINTS[RPC_INTERNAL_ERROR]      = "An unexpected error occurred inside the Photoshop handler. Check the plugin log for details.";
ERROR_HINTS[CUSTOM_ERR_NO_ACTIVE_DOC]     = "Open or create a document before calling document/layer methods.";
ERROR_HINTS[CUSTOM_ERR_LAYER_NOT_FOUND]   = "Use ps.listLayers to see the current layer tree.";
ERROR_HINTS[CUSTOM_ERR_UNSUPPORTED_FORMAT] = "Supported formats: png, jpg, tiff, psd.";
ERROR_HINTS[CUSTOM_ERR_FILE_NOT_FOUND]    = "Verify the path exists and Photoshop has permission to access it.";
ERROR_HINTS[CUSTOM_ERR_SCRIPT_ERROR]      = "The JavaScript expression could not be evaluated. Check syntax and available APIs.";
ERROR_HINTS[CUSTOM_ERR_TIMEOUT]           = "The operation took too long and was cancelled. Try a smaller operation or increase the timeout.";
ERROR_HINTS[CUSTOM_ERR_DISCONNECTED]      = "The UXP plugin lost connection. It will auto-reconnect. Retry the call once reconnected.";

// ── Message builders ──────────────────────────────────────────────────────────

/**
 * Build a hello message (UXP → Python).
 * @param {string} [client="photoshop-uxp"]
 * @param {boolean} [reconnect=false] - True if this is a reconnection.
 * @returns {object}
 */
function buildHello(client, reconnect) {
    const msg = {
        type: "hello",
        protocol: PROTOCOL_NAME,
        version: PROTOCOL_VERSION,
        client: client || "photoshop-uxp",
    };
    if (reconnect) msg.reconnect = true;
    return msg;
}

/**
 * Build a JSON-RPC 2.0 success response.
 * @param {number|string|null} id - Request id
 * @param {*} result - Result value
 * @returns {object}
 */
function rpcSuccess(id, result) {
    return { jsonrpc: "2.0", id, result };
}

/**
 * Build a JSON-RPC 2.0 error response with optional hint.
 * @param {number|string|null} id - Request id (null for parse errors)
 * @param {number} code - Error code
 * @param {string} message - Error message
 * @param {string} [hint] - Actionable suggestion. Auto-populated from known codes if omitted.
 * @param {*} [data] - Optional extra diagnostic data
 * @returns {object}
 */
function rpcError(id, code, message, hint, data) {
    const error = { code, message };
    const h = hint || ERROR_HINTS[code];
    if (h) error.hint = h;
    if (data !== undefined) error.data = data;
    return { jsonrpc: "2.0", id, error };
}

/**
 * Build a progress notification (UXP → Python).
 * @param {number} id - The id of the original request
 * @param {number} current - Current progress value
 * @param {number} total - Total progress value
 * @param {string} [message=""] - Human-readable description
 * @param {string} [stage] - Named stage identifier
 * @returns {object}
 */
function buildProgress(id, current, total, message, stage) {
    const progress = { current, total };
    if (message) progress.message = message;
    if (stage) progress.stage = stage;
    return { jsonrpc: "2.0", id, type: "progress", progress };
}

/**
 * Parse a raw WebSocket message into a JSON-RPC request object.
 * @param {string} raw - Raw message string
 * @returns {{ request: object|null, parseError: object|null }}
 */
function parseRequest(raw) {
    let request;
    try {
        request = JSON.parse(raw);
    } catch (_e) {
        return { request: null, parseError: rpcError(null, RPC_PARSE_ERROR, "Parse error") };
    }
    if (!request || request.jsonrpc !== "2.0" || typeof request.method !== "string") {
        const id = (request && request.id !== undefined) ? request.id : null;
        return { request: null, parseError: rpcError(id, RPC_INVALID_REQUEST, "Invalid Request") };
    }
    return { request, parseError: null };
}

// ── Validators ────────────────────────────────────────────────────────────────

function isHelloAck(msg) { return msg && msg.type === "hello_ack"; }
function isDisconnected(msg) { return msg && msg.type === "disconnected"; }

function checkVersion(version) {
    try {
        return parseInt(version.split(".")[0], 10) === 0;
    } catch (_e) {
        return false;
    }
}

module.exports = {
    PROTOCOL_NAME, PROTOCOL_VERSION,
    RPC_PARSE_ERROR, RPC_INVALID_REQUEST, RPC_METHOD_NOT_FOUND, RPC_INVALID_PARAMS, RPC_INTERNAL_ERROR,
    CUSTOM_ERR_NO_ACTIVE_DOC, CUSTOM_ERR_LAYER_NOT_FOUND, CUSTOM_ERR_UNSUPPORTED_FORMAT,
    CUSTOM_ERR_FILE_NOT_FOUND, CUSTOM_ERR_SCRIPT_ERROR, CUSTOM_ERR_TIMEOUT, CUSTOM_ERR_DISCONNECTED,
    ERROR_HINTS,
    buildHello, rpcSuccess, rpcError, buildProgress, parseRequest,
    isHelloAck, isDisconnected, checkVersion,
};
