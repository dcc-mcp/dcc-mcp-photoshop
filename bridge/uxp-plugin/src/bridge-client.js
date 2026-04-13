/**
 * bridge-client.js — UXP WebSocket CLIENT
 *
 * Connects to the Python WebSocket server (ws://localhost:9001).
 * Receives JSON-RPC 2.0 requests from Python, dispatches to PS handlers,
 * and sends back responses.
 *
 * Reconnects automatically if the connection drops.
 */

"use strict";

const documentHandlers = require("./handlers/document");
const layerHandlers    = require("./handlers/layers");
const scriptHandlers   = require("./handlers/script");
const { rpcSuccess, rpcError, parseRequest, RPC_METHOD_NOT_FOUND, RPC_INTERNAL_ERROR } = require("./utils/jsonrpc");

// Python bridge server — must match bridge.py BRIDGE_SERVER_PORT
const BRIDGE_URL = "ws://localhost:9001";
const RECONNECT_DELAY_MS = 3000;

// All registered method → handler map
const HANDLERS = Object.assign({}, documentHandlers, layerHandlers, scriptHandlers);

let _ws = null;
let _reconnectTimer = null;
let _stopped = false;
let _statusCallback = null;

function _setStatus(status, detail) {
    console.log(`[dcc-mcp] ${status}${detail ? ": " + detail : ""}`);
    if (_statusCallback) _statusCallback(status, detail);
}

/**
 * Register a callback for status changes.
 * @param {function(status: string, detail?: string): void} cb
 */
function onStatusChange(cb) {
    _statusCallback = cb;
}

/**
 * Dispatch a JSON-RPC request to the appropriate Photoshop handler.
 * @param {object} request
 * @returns {Promise<object>} JSON-RPC response
 */
async function _dispatch(request) {
    const { id, method, params = {} } = request;
    const handler = HANDLERS[method];

    if (!handler) {
        return rpcError(id, RPC_METHOD_NOT_FOUND, `Method not found: ${method}`);
    }

    try {
        const result = await handler(params);
        return rpcSuccess(id, result);
    } catch (err) {
        const code = err.code || RPC_INTERNAL_ERROR;
        return rpcError(id, code, err.message || String(err));
    }
}

/**
 * Connect to the Python WebSocket bridge server.
 */
function connect() {
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) {
        return;
    }

    _stopped = false;
    _setStatus("Connecting", BRIDGE_URL);

    try {
        _ws = new WebSocket(BRIDGE_URL);
    } catch (err) {
        _setStatus("Disconnected", `Failed to create WebSocket: ${err.message}`);
        _scheduleReconnect();
        return;
    }

    _ws.onopen = () => {
        _setStatus("Connected", `Bridge connected to Python at ${BRIDGE_URL}`);
        // Announce ourselves to the Python server
        _ws.send(JSON.stringify({ type: "hello", client: "photoshop-uxp", version: "0.1.0" }));
    };

    _ws.onmessage = async (event) => {
        const raw = typeof event.data === "string" ? event.data : event.data.toString();

        let request;
        try {
            request = JSON.parse(raw);
        } catch (_e) {
            console.error("[dcc-mcp] Invalid JSON from server:", raw.slice(0, 200));
            return;
        }

        // Handle non-RPC messages (e.g. server acknowledgement)
        if (!request.method && request.type) {
            console.log("[dcc-mcp] Server message:", request.type);
            return;
        }

        const { request: rpcReq, parseError } = parseRequest(raw);
        if (parseError) {
            _ws.send(JSON.stringify(parseError));
            return;
        }

        const response = await _dispatch(rpcReq);
        _ws.send(JSON.stringify(response));
    };

    _ws.onerror = (err) => {
        _setStatus("Error", String(err.message || err));
    };

    _ws.onclose = (event) => {
        _ws = null;
        if (!_stopped) {
            _setStatus("Disconnected", `Code ${event.code} — reconnecting in ${RECONNECT_DELAY_MS / 1000}s`);
            _scheduleReconnect();
        } else {
            _setStatus("Disconnected", "Stopped by user");
        }
    };
}

function _scheduleReconnect() {
    if (_reconnectTimer) return;
    _reconnectTimer = setTimeout(() => {
        _reconnectTimer = null;
        if (!_stopped) connect();
    }, RECONNECT_DELAY_MS);
}

/**
 * Disconnect and stop auto-reconnect.
 */
function disconnect() {
    _stopped = true;
    if (_reconnectTimer) {
        clearTimeout(_reconnectTimer);
        _reconnectTimer = null;
    }
    if (_ws) {
        _ws.close();
        _ws = null;
    }
    _setStatus("Disconnected", "Disconnected by user");
}

module.exports = { connect, disconnect, onStatusChange };
