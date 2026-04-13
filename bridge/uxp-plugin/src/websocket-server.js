/**
 * WebSocket server that listens for JSON-RPC 2.0 requests from the Python bridge.
 *
 * UXP uses a non-standard WebSocket server API accessed via:
 *   require("uxp").networking.createWebSocketServer(port)
 *
 * Reference:
 *   https://developer.adobe.com/photoshop/uxp/2022/uxp-api/reference-js/Modules/network/WebSocket/
 */

"use strict";

const { rpcSuccess, rpcError, parseRequest, RPC_METHOD_NOT_FOUND, RPC_INTERNAL_ERROR } = require("./utils/jsonrpc");

// Handler registries loaded from handler modules
const HANDLERS = {};

/**
 * Register a map of method -> async handler function.
 * @param {object} handlerMap - { "method.name": asyncFunction, ... }
 */
function registerHandlers(handlerMap) {
    Object.assign(HANDLERS, handlerMap);
}

/**
 * Dispatch a single parsed JSON-RPC request to the appropriate handler.
 * Returns a JSON-RPC response object (never throws).
 * @param {object} request - Already-parsed JSON-RPC request
 * @returns {Promise<object>} JSON-RPC response object
 */
async function dispatch(request) {
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
 * Handle a single WebSocket connection from the Python bridge.
 * @param {WebSocket} ws - UXP WebSocket connection object
 */
function handleConnection(ws) {
    console.log("[dcc-mcp] Python bridge connected");

    ws.onmessage = async (event) => {
        const raw = typeof event === "string" ? event : event.data;
        const { request, parseError } = parseRequest(raw);

        if (parseError) {
            ws.send(JSON.stringify(parseError));
            return;
        }

        const response = await dispatch(request);
        ws.send(JSON.stringify(response));
    };

    ws.onclose = () => {
        console.log("[dcc-mcp] Python bridge disconnected");
    };

    ws.onerror = (err) => {
        console.error("[dcc-mcp] WebSocket error:", err);
    };
}

/**
 * Start the WebSocket server on the given port.
 * Returns the server instance (call .close() to stop).
 * @param {number} port
 * @returns {object} UXP WebSocket server instance
 */
function startServer(port) {
    const { networking } = require("uxp");

    // UXP WebSocket server API (available in Photoshop 2022+ / UXP 5.x+)
    const server = networking.createWebSocketServer(port);

    server.onconnection = (ws) => {
        handleConnection(ws);
    };

    server.onerror = (err) => {
        console.error(`[dcc-mcp] WebSocket server error on port ${port}:`, err);
    };

    console.log(`[dcc-mcp] WebSocket server started on port ${port}`);
    return server;
}

module.exports = { startServer, registerHandlers, dispatch };
