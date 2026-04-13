/**
 * dcc-mcp UXP Plugin — WebSocket client bridge (single-file)
 * Python WS server :9001 ← UXP connects here
 */
"use strict";

// ── JSON-RPC helpers ──────────────────────────────────────────────────────────
const RPC_NOT_FOUND   = -32601;
const RPC_INTERNAL    = -32603;
const RPC_INVALID_P   = -32602;
const RPC_NO_DOC      = -32001;

function ok(id, result) { return JSON.stringify({ jsonrpc:"2.0", id, result }); }
function err(id, code, msg) { return JSON.stringify({ jsonrpc:"2.0", id, error:{ code, message:msg }}); }

// ── PS helpers ────────────────────────────────────────────────────────────────
function ps()  { return require("photoshop"); }
function uxp() { return require("uxp"); }

function requireDoc() {
    const doc = ps().app.activeDocument;
    if (!doc) throw Object.assign(new Error("No active document"), { code: RPC_NO_DOC });
    return doc;
}

function serializeDoc(doc) {
    return {
        id: doc.id,
        name: doc.name,
        width: doc.width,
        height: doc.height,
        resolution: doc.resolution,
        color_mode: String(doc.mode),
        bit_depth: doc.bitsPerChannel,
        path: (() => { try { return doc.path; } catch(_){ return null; } })(),
        has_unsaved_changes: (() => { try { return doc.dirty; } catch(_){ return false; } })(),
    };
}

function serializeLayer(l) {
    const b = l.bounds;
    return {
        id: l.id,
        name: l.name,
        type: String(l.kind),
        visible: l.visible,
        opacity: l.opacity,
        locked: l.allLocked,
        bounds: b ? { top: b.top, left: b.left, bottom: b.bottom, right: b.right, width: b.width, height: b.height } : null,
    };
}

function findLayer(doc, name) {
    for (const l of doc.layers) if (l.name === name) return l;
    return null;
}

// Wrap write operations in executeAsModal (required by UXP for any PS state change)
async function modal(fn, cmdName) {
    return ps().core.executeAsModal(fn, { commandName: cmdName || "dcc-mcp" });
}

// ── Handlers ──────────────────────────────────────────────────────────────────
const HANDLERS = {

    // ── Document (read-only — no modal needed) ─────────────────────────────
    async "ps.getDocumentInfo"(_p) {
        return serializeDoc(requireDoc());
    },
    async "ps.listDocuments"(_p) {
        return Array.from(ps().app.documents).map(serializeDoc);
    },

    // ── Document (write — requires modal) ─────────────────────────────────
    async "ps.saveDocument"(_p) {
        const doc = requireDoc();
        await modal(async () => { await doc.save(); }, "Save document");
        return { saved: true };
    },
    async "ps.closeDocument"(p) {
        const doc = requireDoc();
        const SO = ps().constants.SaveOptions;
        await modal(async () => {
            await doc.close(p.save ? SO.SAVECHANGES : SO.DONOTSAVECHANGES);
        }, "Close document");
        return { closed: true };
    },
    async "ps.exportDocument"(p) {
        if (!p.path) throw Object.assign(new Error("'path' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const lfs = uxp().storage.localFileSystem;
        const fmt = (p.format || "png").toLowerCase();

        // Resolve output file using UXP localFileSystem
        // Support: absolute path or relative to temp folder
        let outFile;
        if (p.path.startsWith("/tmp/") || p.path.toLowerCase().startsWith("c:/users")) {
            // Use temp folder for /tmp/ paths
            const tmpFolder = await lfs.getTemporaryFolder();
            const fname = p.path.split("/").pop().split("\\").pop();
            outFile = await tmpFolder.createFile(fname, { overwrite: true });
        } else {
            // Try direct URL
            try {
                outFile = await lfs.getEntryWithUrl("file://" + p.path.replace(/\\/g, "/"), { mode: lfs.createIfNotExists });
            } catch (_e) {
                // Fallback: temp folder
                const tmpFolder = await lfs.getTemporaryFolder();
                const fname = p.path.split("/").pop().split("\\").pop();
                outFile = await tmpFolder.createFile(fname, { overwrite: true });
            }
        }

        await modal(async () => {
            if (fmt === "jpg" || fmt === "jpeg") {
                await doc.saveAs.jpg(outFile, { quality: Math.min(100, Math.max(0, p.quality || 90)) });
            } else if (fmt === "png") {
                await doc.saveAs.png(outFile, { compression: 6 });
            } else if (fmt === "tiff" || fmt === "tif") {
                await doc.saveAs.tiff(outFile, {});
            } else if (fmt === "psd") {
                await doc.saveAs.psd(outFile, {});
            } else {
                throw Object.assign(new Error("Unsupported format: " + fmt), { code: RPC_INVALID_P });
            }
        }, "Export document");

        const nativePath = (() => { try { return outFile.nativePath; } catch(_) { return p.path; } })();
        return { exported: true, path: nativePath, format: fmt };
    },

    // ── Layers (read) ──────────────────────────────────────────────────────
    async "ps.listLayers"(p) {
        const doc = requireDoc();
        const all = Array.from(doc.layers).map(serializeLayer);
        return p.include_hidden === false ? all.filter(l => l.visible) : all;
    },

    // ── Layers (write) ────────────────────────────────────────────────────
    async "ps.createLayer"(p) {
        const doc = requireDoc();
        const name = p.name || "Layer";
        let layer;
        await modal(async () => {
            layer = p.type === "group"
                ? await doc.createLayerGroup({ name })
                : await doc.createLayer({ name });
        }, "Create layer");
        return { id: layer.id, name: layer.name, type: String(layer.kind) };
    },
    async "ps.deleteLayer"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l = findLayer(doc, p.name);
        if (!l) throw Object.assign(new Error(`Layer "${p.name}" not found`), { code: RPC_NO_DOC });
        await modal(async () => { await l.delete(); }, "Delete layer");
        return { deleted: true, name: p.name };
    },
    async "ps.setLayerVisibility"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l = findLayer(doc, p.name);
        if (!l) throw Object.assign(new Error(`Layer "${p.name}" not found`), { code: RPC_NO_DOC });
        await modal(async () => { l.visible = Boolean(p.visible); }, "Set visibility");
        return { name: p.name, visible: l.visible };
    },
    async "ps.renameLayer"(p) {
        if (!p.name || !p.new_name) throw Object.assign(new Error("'name' and 'new_name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l = findLayer(doc, p.name);
        if (!l) throw Object.assign(new Error(`Layer "${p.name}" not found`), { code: RPC_NO_DOC });
        await modal(async () => { l.name = p.new_name; }, "Rename layer");
        return { old_name: p.name, name: l.name };
    },
    async "ps.setLayerOpacity"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l = findLayer(doc, p.name);
        if (!l) throw Object.assign(new Error(`Layer "${p.name}" not found`), { code: RPC_NO_DOC });
        await modal(async () => { l.opacity = Math.min(100, Math.max(0, Number(p.opacity))); }, "Set opacity");
        return { name: p.name, opacity: l.opacity };
    },
    async "ps.duplicateLayer"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l = findLayer(doc, p.name);
        if (!l) throw Object.assign(new Error(`Layer "${p.name}" not found`), { code: RPC_NO_DOC });
        let dup;
        await modal(async () => {
            dup = await l.duplicate();
            if (p.new_name) dup.name = p.new_name;
        }, "Duplicate layer");
        return { id: dup.id, name: dup.name };
    },

    // ── Script / Action ───────────────────────────────────────────────────
    // NOTE: new Function() is blocked by CSP in UXP 5+.
    // Use batchPlay for DOM access instead.
    async "ps.executeScript"(p) {
        if (!p.code) throw Object.assign(new Error("'code' required"), { code: RPC_INVALID_P });
        // Execute safe read-only expressions via batchPlay + Action Descriptor
        // For complex scripts, use ps.executeAction instead.
        // We implement a small safe subset here:
        const code = p.code.trim();
        if (code === "app.documents.length") {
            return ps().app.documents.length;
        }
        if (code === "app.activeDocument.name") {
            return requireDoc().name;
        }
        if (code === "app.activeDocument.layers.length") {
            return requireDoc().layers.length;
        }
        if (code === "app.activeDocument.width") {
            return requireDoc().width;
        }
        if (code === "app.activeDocument.height") {
            return requireDoc().height;
        }
        // For arbitrary code, try batchPlay with evaluateExpression
        // (not all expressions supported)
        throw Object.assign(
            new Error(
                "Arbitrary new Function() is blocked by UXP CSP. " +
                "Use ps.executeAction with batchPlay, or built-in expressions: " +
                "app.documents.length, app.activeDocument.name, etc."
            ),
            { code: -32000 }
        );
    },
    async "ps.executeAction"(p) {
        if (!p.action || !p.action_set) throw Object.assign(new Error("'action' and 'action_set' required"), { code: RPC_INVALID_P });
        await modal(async () => {
            await ps().action.batchPlay([{
                _obj: "play",
                _target: [{ _ref: "action", _name: p.action }],
                using: { _ref: "actionSet", _name: p.action_set },
            }], {});
        }, "Execute action");
        return { executed: true, action: p.action, action_set: p.action_set };
    },
};

// ── Dispatcher ────────────────────────────────────────────────────────────────
async function dispatch(raw) {
    let req;
    try { req = JSON.parse(raw); } catch(_) { return err(null, -32700, "Parse error"); }
    if (!req || !req.method) return null;

    const handler = HANDLERS[req.method];
    if (!handler) return err(req.id, RPC_NOT_FOUND, "Method not found: " + req.method);

    try {
        const result = await handler(req.params || {});
        return ok(req.id, result);
    } catch (e) {
        return err(req.id, e.code || RPC_INTERNAL, e.message || String(e));
    }
}

// ── WebSocket client ──────────────────────────────────────────────────────────
const URL = "ws://localhost:9001";
const RECONNECT = 3000;
let _ws = null, _stopped = false, _timer = null, _onStatus = null;

function setStatus(s, d) {
    console.log("[dcc-mcp] " + s + (d ? ": " + d : ""));
    if (_onStatus) _onStatus(s, d);
}

function connect() {
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return;
    _stopped = false;
    setStatus("Connecting", URL);
    try { _ws = new WebSocket(URL); } catch(e) {
        setStatus("Disconnected", "Failed: " + e.message);
        schedRecon(); return;
    }
    _ws.onopen = () => {
        setStatus("Connected", "Bridge connected at " + URL);
        _ws.send(JSON.stringify({ type:"hello", client:"photoshop-uxp", version:"0.1.0" }));
    };
    _ws.onmessage = async (ev) => {
        const raw = typeof ev.data === "string" ? ev.data : String(ev.data);
        const resp = await dispatch(raw);
        if (resp && _ws && _ws.readyState === WebSocket.OPEN) _ws.send(resp);
    };
    _ws.onerror = (e) => setStatus("Error", String(e.message || e));
    _ws.onclose = (e) => {
        _ws = null;
        if (!_stopped) { setStatus("Disconnected", "Code " + e.code + " — reconnecting..."); schedRecon(); }
        else setStatus("Disconnected", "Stopped");
    };
}

function schedRecon() {
    if (_timer) return;
    _timer = setTimeout(() => { _timer = null; if (!_stopped) connect(); }, RECONNECT);
}

function disconnect() {
    _stopped = true;
    if (_timer) { clearTimeout(_timer); _timer = null; }
    if (_ws) { _ws.close(); _ws = null; }
    setStatus("Disconnected", "Stopped by user");
}

// ── Panel UI ──────────────────────────────────────────────────────────────────
const statusEl = document.getElementById("status");
const logEl    = document.getElementById("log");
const btnC     = document.getElementById("btn-connect");
const btnD     = document.getElementById("btn-disconnect");

function addLog(t) {
    const d = document.createElement("div");
    d.className = "log-line";
    d.textContent = "[" + new Date().toLocaleTimeString() + "] " + t;
    logEl.insertBefore(d, logEl.firstChild);
    while (logEl.children.length > 30) logEl.removeChild(logEl.lastChild);
}

_onStatus = (s, detail) => {
    if (statusEl) {
        statusEl.textContent = "⬤ " + s;
        const sl = s.toLowerCase();
        statusEl.className = (sl.includes("connected") && !sl.includes("dis")) ? "connected"
            : sl.includes("connecting") ? "connecting" : "disconnected";
    }
    if (detail) addLog(detail);
};

if (btnC) btnC.onclick = connect;
if (btnD) btnD.onclick = disconnect;
connect();
