/**
 * dcc-mcp UXP Plugin for Adobe Photoshop
 *
 * Starts a WebSocket server that accepts JSON-RPC 2.0 messages from the
 * Python bridge (dcc-mcp-photoshop) and executes Photoshop UXP API calls.
 *
 * Status: PLACEHOLDER — implementation pending
 * Port: 3000 (configurable)
 */

// TODO: Implement WebSocket server using UXP network APIs
// TODO: Implement JSON-RPC 2.0 dispatcher
// TODO: Implement Photoshop API handlers

const WS_PORT = 3000;

/**
 * Plugin entry point — called when Photoshop loads the plugin.
 */
async function main() {
    console.log("[dcc-mcp] Plugin loaded — WebSocket server placeholder");
    console.log(`[dcc-mcp] TODO: Start WebSocket server on port ${WS_PORT}`);

    // TODO: Start WebSocket server
    // const { WebSocket } = require("uxp").network;
    // const server = new WebSocket.Server({ port: WS_PORT });
    // server.on("connection", handleConnection);
}

/**
 * Handle incoming WebSocket connection from Python bridge.
 * @param {WebSocket} ws - The WebSocket connection
 */
function handleConnection(ws) {
    console.log("[dcc-mcp] Python bridge connected");

    ws.on("message", async (data) => {
        let request;
        try {
            request = JSON.parse(data);
        } catch (e) {
            ws.send(JSON.stringify({
                jsonrpc: "2.0",
                id: null,
                error: { code: -32700, message: "Parse error" }
            }));
            return;
        }

        const response = await dispatch(request);
        ws.send(JSON.stringify(response));
    });

    ws.on("close", () => {
        console.log("[dcc-mcp] Python bridge disconnected");
    });
}

/**
 * Dispatch a JSON-RPC request to the appropriate handler.
 * @param {object} request - JSON-RPC 2.0 request object
 * @returns {object} JSON-RPC 2.0 response object
 */
async function dispatch(request) {
    const { id, method, params = {} } = request;

    // TODO: Implement handlers
    const handlers = {
        "ps.getDocumentInfo": getDocumentInfo,
        "ps.listDocuments": listDocuments,
        "ps.listLayers": listLayers,
        "ps.executeScript": executeScript,
    };

    const handler = handlers[method];
    if (!handler) {
        return {
            jsonrpc: "2.0",
            id,
            error: { code: -32601, message: `Method not found: ${method}` }
        };
    }

    try {
        const result = await handler(params);
        return { jsonrpc: "2.0", id, result };
    } catch (e) {
        return {
            jsonrpc: "2.0",
            id,
            error: { code: -32603, message: e.message || String(e) }
        };
    }
}

// ── Handler stubs (TODO: implement) ──

async function getDocumentInfo(_params) {
    // TODO: const ps = require("photoshop");
    // TODO: const doc = ps.app.activeDocument;
    // TODO: return { name: doc.name, width: doc.width, height: doc.height, ... };
    throw new Error("getDocumentInfo not implemented yet");
}

async function listDocuments(_params) {
    // TODO: const ps = require("photoshop");
    // TODO: return ps.app.documents.map(d => ({ name: d.name, id: d.id }));
    throw new Error("listDocuments not implemented yet");
}

async function listLayers(params) {
    // TODO: const ps = require("photoshop");
    // TODO: const doc = ps.app.activeDocument;
    // TODO: return doc.layers.map(l => ({ name: l.name, type: l.kind, visible: l.visible }));
    throw new Error("listLayers not implemented yet");
}

async function executeScript(params) {
    // TODO: const ps = require("photoshop");
    // TODO: return await ps.action.batchPlay([...], {});
    throw new Error("executeScript not implemented yet");
}

module.exports = { main };
