/**
 * JSON-RPC 2.0 helpers.
 *
 * See: https://www.jsonrpc.org/specification
 */

"use strict";

// Standard JSON-RPC 2.0 error codes
const RPC_PARSE_ERROR = -32700;
const RPC_INVALID_REQUEST = -32600;
const RPC_METHOD_NOT_FOUND = -32601;
const RPC_INVALID_PARAMS = -32602;
const RPC_INTERNAL_ERROR = -32603;

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
 * Build a JSON-RPC 2.0 error response.
 * @param {number|string|null} id - Request id (null for parse errors)
 * @param {number} code - Error code
 * @param {string} message - Error message
 * @param {*} [data] - Optional extra data
 * @returns {object}
 */
function rpcError(id, code, message, data) {
    const error = { code, message };
    if (data !== undefined) error.data = data;
    return { jsonrpc: "2.0", id, error };
}

/**
 * Parse a raw WebSocket message into a JSON-RPC request object.
 * Returns null and sends a parse-error response if the message is invalid.
 * @param {string} raw - Raw message string
 * @returns {{ request: object|null, parseError: object|null }}
 */
function parseRequest(raw) {
    let request;
    try {
        request = JSON.parse(raw);
    } catch (_e) {
        return {
            request: null,
            parseError: rpcError(null, RPC_PARSE_ERROR, "Parse error"),
        };
    }

    if (!request || request.jsonrpc !== "2.0" || typeof request.method !== "string") {
        return {
            request: null,
            parseError: rpcError(request.id ?? null, RPC_INVALID_REQUEST, "Invalid Request"),
        };
    }

    return { request, parseError: null };
}

module.exports = {
    RPC_PARSE_ERROR,
    RPC_INVALID_REQUEST,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_PARAMS,
    RPC_INTERNAL_ERROR,
    rpcSuccess,
    rpcError,
    parseRequest,
};
