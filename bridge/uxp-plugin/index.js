/**
 * dcc-mcp UXP Plugin — WebSocket client bridge (single-file)
 * Python WS server :9001 ← UXP connects here
 *
 * Features:
 *   - Exponential back-off reconnect (3s → 6s → 12s → … max 60s)
 *   - Persistent local log file (UXP PluginData/bridge.log)
 *   - Full Photoshop document/layer/image/text operation handlers
 */
"use strict";

// ── JSON-RPC error codes ───────────────────────────────────────────────────────
const RPC_NOT_FOUND   = -32601;
const RPC_INTERNAL    = -32603;
const RPC_INVALID_P   = -32602;
const RPC_NO_DOC      = -32001;

function ok(id, result) { return JSON.stringify({ jsonrpc:"2.0", id, result }); }
function err(id, code, msg) { return JSON.stringify({ jsonrpc:"2.0", id, error:{ code, message:msg }}); }

// ── PS / UXP module helpers ────────────────────────────────────────────────────
function ps()  { return require("photoshop"); }
function uxp() { return require("uxp"); }

function requireDoc() {
    const doc = ps().app.activeDocument;
    if (!doc) throw Object.assign(new Error("No active document"), { code: RPC_NO_DOC });
    return doc;
}

// ── Hex color → {red, green, blue} ────────────────────────────────────────────
function hexToRgb(hex) {
    const h = hex.replace("#", "");
    return {
        red:   parseInt(h.substring(0,2), 16),
        green: parseInt(h.substring(2,4), 16),
        blue:  parseInt(h.substring(4,6), 16),
    };
}

// ── Blend mode string → UXP BlendMode constant ────────────────────────────────
function blendModeConst(name) {
    const BM = ps().constants.BlendMode;
    const map = {
        normal: BM.NORMAL, dissolve: BM.DISSOLVE,
        darken: BM.DARKEN, multiply: BM.MULTIPLY, color_burn: BM.COLORBURN,
        linear_burn: BM.LINEARBURN, darker_color: BM.DARKERCOLOR,
        lighten: BM.LIGHTEN, screen: BM.SCREEN, color_dodge: BM.COLORDODGE,
        linear_dodge: BM.LINEARDODGE, lighter_color: BM.LIGHTERCOLOR,
        overlay: BM.OVERLAY, soft_light: BM.SOFTLIGHT, hard_light: BM.HARDLIGHT,
        vivid_light: BM.VIVIDLIGHT, linear_light: BM.LINEARLIGHT,
        pin_light: BM.PINLIGHT, hard_mix: BM.HARDMIX,
        difference: BM.DIFFERENCE, exclusion: BM.EXCLUSION,
        subtract: BM.SUBTRACT, divide: BM.DIVIDE,
        hue: BM.HUE, saturation: BM.SATURATION,
        color: BM.COLOR, luminosity: BM.LUMINOSITY,
    };
    return map[name.toLowerCase()] || BM.NORMAL;
}

// ── Serialize helpers ──────────────────────────────────────────────────────────
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

function findLayerRequired(doc, name) {
    const l = findLayer(doc, name);
    if (!l) throw Object.assign(new Error(`Layer "${name}" not found`), { code: RPC_NO_DOC });
    return l;
}

// Wrap write operations in executeAsModal (required for any PS state change)
async function modal(fn, cmdName) {
    return ps().core.executeAsModal(fn, { commandName: cmdName || "dcc-mcp" });
}

// ── Local persistent log ───────────────────────────────────────────────────────
let _logFile   = null;   // UXP File entry for bridge.log
let _logBuffer = [];     // Lines queued before file is ready

async function initLogFile() {
    try {
        const lfs    = uxp().storage.localFileSystem;
        const folder = await lfs.getDataFolder();
        _logFile = await folder.createFile("bridge.log", { overwrite: false });
        // Drain buffer
        if (_logBuffer.length > 0) {
            const lines = _logBuffer.join("\n") + "\n";
            _logBuffer = [];
            await _logFile.write(lines, { append: true });
        }
        writeLog("--- log session start ---");
    } catch (e) {
        console.warn("[dcc-mcp] Could not open log file:", e);
    }
}

async function writeLog(line) {
    const ts  = new Date().toISOString();
    const msg = `[${ts}] ${line}`;
    console.log("[dcc-mcp]", line);
    if (!_logFile) {
        _logBuffer.push(msg);
        return;
    }
    try {
        await _logFile.write(msg + "\n", { append: true });
    } catch (_) {
        _logBuffer.push(msg);
    }
}

// ── Handlers ──────────────────────────────────────────────────────────────────
const HANDLERS = {

    // ── Document (read-only) ───────────────────────────────────────────────
    async "ps.getDocumentInfo"(_p) {
        return serializeDoc(requireDoc());
    },
    async "ps.listDocuments"(_p) {
        return Array.from(ps().app.documents).map(serializeDoc);
    },

    // ── Document (write) ──────────────────────────────────────────────────
    async "ps.createDocument"(p) {
        const CM = ps().constants.ColorMode;
        const colorModeMap = {
            rgb:       CM.RGB,
            cmyk:      CM.CMYK,
            grayscale: CM.GRAYSCALE,
            lab:       CM.LAB,
        };
        const fillMap = {
            white:       ps().constants.DocumentFill.WHITE,
            black:       ps().constants.DocumentFill.BLACK,
            transparent: ps().constants.DocumentFill.TRANSPARENT,
            background:  ps().constants.DocumentFill.BACKGROUNDCOLOR,
        };
        let doc;
        await modal(async () => {
            doc = await ps().app.documents.add({
                name:       p.name || "Untitled",
                width:      p.width  || 1920,
                height:     p.height || 1080,
                resolution: p.resolution || 72,
                mode:       colorModeMap[(p.color_mode || "rgb").toLowerCase()] || CM.RGB,
                bitDepth:   p.bit_depth  || 8,
                fill:       fillMap[(p.fill || "white").toLowerCase()] || ps().constants.DocumentFill.WHITE,
            });
        }, "Create document");
        return serializeDoc(doc);
    },
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

        let outFile;
        if (p.path.startsWith("/tmp/") || p.path.toLowerCase().startsWith("c:/users")) {
            const tmpFolder = await lfs.getTemporaryFolder();
            const fname = p.path.split("/").pop().split("\\").pop();
            outFile = await tmpFolder.createFile(fname, { overwrite: true });
        } else {
            try {
                outFile = await lfs.getEntryWithUrl("file://" + p.path.replace(/\\/g, "/"), { mode: lfs.createIfNotExists });
            } catch (_e) {
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

    // ── Resize ────────────────────────────────────────────────────────────
    async "ps.resizeCanvas"(p) {
        if (!p.width || !p.height) throw Object.assign(new Error("'width' and 'height' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const anchorMap = {
            top_left:      ps().constants.AnchorPosition.TOPLEFT,
            top_center:    ps().constants.AnchorPosition.TOPCENTER,
            top_right:     ps().constants.AnchorPosition.TOPRIGHT,
            middle_left:   ps().constants.AnchorPosition.MIDDLELEFT,
            center:        ps().constants.AnchorPosition.MIDDLECENTER,
            middle_right:  ps().constants.AnchorPosition.MIDDLERIGHT,
            bottom_left:   ps().constants.AnchorPosition.BOTTOMLEFT,
            bottom_center: ps().constants.AnchorPosition.BOTTOMCENTER,
            bottom_right:  ps().constants.AnchorPosition.BOTTOMRIGHT,
        };
        const anchor = anchorMap[(p.anchor || "center").toLowerCase()] || ps().constants.AnchorPosition.MIDDLECENTER;
        await modal(async () => {
            await doc.resizeCanvas(p.width, p.height, anchor);
        }, "Resize canvas");
        return { width: doc.width, height: doc.height };
    },
    async "ps.resizeImage"(p) {
        if (!p.width || !p.height) throw Object.assign(new Error("'width' and 'height' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const rsMap = {
            bicubic:           ps().constants.ResampleMethod.BICUBIC,
            bilinear:          ps().constants.ResampleMethod.BILINEAR,
            nearest:           ps().constants.ResampleMethod.NEARESTNEIGHBOR,
            preserve_details:  ps().constants.ResampleMethod.PRESERVEDETAILS,
            bicubic_smoother:  ps().constants.ResampleMethod.BICUBICSMOOTHER,
            bicubic_sharper:   ps().constants.ResampleMethod.BICUBICSHARPER,
        };
        const method = rsMap[(p.resample || "bicubic").toLowerCase()] || ps().constants.ResampleMethod.BICUBIC;
        await modal(async () => {
            await doc.resizeImage(p.width, p.height, null, method);
        }, "Resize image");
        return { width: doc.width, height: doc.height };
    },

    // ── Flatten / Merge ───────────────────────────────────────────────────
    async "ps.flattenImage"(_p) {
        const doc = requireDoc();
        await modal(async () => { await doc.flatten(); }, "Flatten image");
        return { flattened: true };
    },
    async "ps.mergeVisibleLayers"(_p) {
        const doc = requireDoc();
        let merged;
        await modal(async () => { merged = await doc.mergeVisibleLayers(); }, "Merge visible layers");
        return { merged: true, layer_name: merged ? merged.name : null };
    },

    // ── Layers (read) ─────────────────────────────────────────────────────
    async "ps.listLayers"(p) {
        const doc = requireDoc();
        const all = Array.from(doc.layers).map(serializeLayer);
        return p.include_hidden === false ? all.filter(l => l.visible) : all;
    },

    // ── Layers (write) ────────────────────────────────────────────────────
    async "ps.createLayer"(p) {
        const doc  = requireDoc();
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
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => { await l.delete(); }, "Delete layer");
        return { deleted: true, name: p.name };
    },
    async "ps.setLayerVisibility"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => { l.visible = Boolean(p.visible); }, "Set visibility");
        return { name: p.name, visible: l.visible };
    },
    async "ps.renameLayer"(p) {
        if (!p.name || !p.new_name) throw Object.assign(new Error("'name' and 'new_name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => { l.name = p.new_name; }, "Rename layer");
        return { old_name: p.name, name: l.name };
    },
    async "ps.setLayerOpacity"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => { l.opacity = Math.min(100, Math.max(0, Number(p.opacity))); }, "Set opacity");
        return { name: p.name, opacity: l.opacity };
    },
    async "ps.duplicateLayer"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        let dup;
        await modal(async () => {
            dup = await l.duplicate();
            if (p.new_name) dup.name = p.new_name;
        }, "Duplicate layer");
        return { id: dup.id, name: dup.name };
    },
    async "ps.setLayerBlendMode"(p) {
        if (!p.name || !p.blend_mode) throw Object.assign(new Error("'name' and 'blend_mode' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => { l.blendMode = blendModeConst(p.blend_mode); }, "Set blend mode");
        return { name: p.name, blend_mode: p.blend_mode };
    },
    async "ps.fillLayer"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        const color = p.color || "#ffffff";
        const opacity = Math.min(100, Math.max(0, Number(p.opacity || 100)));
        await modal(async () => {
            doc.activeLayers = [l];
            if (color === "transparent") {
                // Clear fill
                await ps().action.batchPlay([{
                    _obj: "delete",
                    _target: [{ _ref: "layer", _enum: "ordinal", _value: "targetEnum" }],
                    apply: true,
                }], {});
            } else {
                const rgb = hexToRgb(color);
                const solidColor = new ps().SolidColor();
                solidColor.rgb.red   = rgb.red;
                solidColor.rgb.green = rgb.green;
                solidColor.rgb.blue  = rgb.blue;
                await ps().action.batchPlay([{
                    _obj: "fill",
                    using: { _enum: "fillContents", _value: "color" },
                    color: { _obj: "RGBColor", red: rgb.red, green: rgb.green, blue: rgb.blue },
                    opacity: { _unit: "percentUnit", _value: opacity },
                    mode: { _enum: "blendMode", _value: "normal" },
                    preserveTransparency: false,
                }], { modalBehavior: "execute" });
            }
        }, "Fill layer");
        return { filled: true, name: p.name, color: color };
    },

    // ── Text layers ───────────────────────────────────────────────────────
    async "ps.createTextLayer"(p) {
        if (!p.content) throw Object.assign(new Error("'content' required"), { code: RPC_INVALID_P });
        const doc  = requireDoc();
        let layer;
        await modal(async () => {
            layer = await doc.createLayer({ name: p.name || p.content.substring(0, 20) });
            const textItem = layer.textItem;
            textItem.contents = p.content;
            textItem.position = [p.x || 100, p.y || 100];
            if (p.font) textItem.font = p.font;
            if (p.size) textItem.size = p.size;
            if (p.color) {
                const rgb = hexToRgb(p.color);
                const c   = new ps().SolidColor();
                c.rgb.red = rgb.red; c.rgb.green = rgb.green; c.rgb.blue = rgb.blue;
                textItem.color = c;
            }
            if (p.alignment) {
                const alignMap = {
                    left:   ps().constants.Justification.LEFT,
                    center: ps().constants.Justification.CENTER,
                    right:  ps().constants.Justification.RIGHT,
                };
                textItem.justification = alignMap[p.alignment.toLowerCase()] || ps().constants.Justification.LEFT;
            }
            if (p.bold !== undefined)   textItem.fauxBold   = Boolean(p.bold);
            if (p.italic !== undefined) textItem.fauxItalic = Boolean(p.italic);
        }, "Create text layer");
        return { id: layer.id, name: layer.name, content: p.content };
    },
    async "ps.updateTextLayer"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        await modal(async () => {
            const t = l.textItem;
            if (!t) throw Object.assign(new Error(`Layer "${p.name}" is not a text layer`), { code: RPC_INVALID_P });
            if (p.content !== undefined)   t.contents   = p.content;
            if (p.font    !== undefined)   t.font       = p.font;
            if (p.size    !== undefined)   t.size       = p.size;
            if (p.color   !== undefined) {
                const rgb = hexToRgb(p.color);
                const c   = new ps().SolidColor();
                c.rgb.red = rgb.red; c.rgb.green = rgb.green; c.rgb.blue = rgb.blue;
                t.color = c;
            }
            if (p.alignment !== undefined) {
                const alignMap = {
                    left:   ps().constants.Justification.LEFT,
                    center: ps().constants.Justification.CENTER,
                    right:  ps().constants.Justification.RIGHT,
                };
                t.justification = alignMap[p.alignment.toLowerCase()] || ps().constants.Justification.LEFT;
            }
            if (p.bold   !== undefined) t.fauxBold   = Boolean(p.bold);
            if (p.italic !== undefined) t.fauxItalic = Boolean(p.italic);
        }, "Update text layer");
        return { name: p.name, content: l.textItem ? l.textItem.contents : null };
    },
    async "ps.getTextLayerInfo"(p) {
        if (!p.name) throw Object.assign(new Error("'name' required"), { code: RPC_INVALID_P });
        const doc = requireDoc();
        const l   = findLayerRequired(doc, p.name);
        const t   = l.textItem;
        if (!t) throw Object.assign(new Error(`Layer "${p.name}" is not a text layer`), { code: RPC_INVALID_P });
        const color = (() => {
            try {
                const c = t.color.rgb;
                return "#" + [c.red, c.green, c.blue].map(v => Math.round(v).toString(16).padStart(2,"0")).join("");
            } catch(_) { return null; }
        })();
        return {
            name:      l.name,
            content:   t.contents,
            font:      t.font,
            size:      t.size,
            color,
            alignment: String(t.justification),
            bold:      t.fauxBold,
            italic:    t.fauxItalic,
        };
    },

    // ── Script / Action ───────────────────────────────────────────────────
    async "ps.executeScript"(p) {
        if (!p.code) throw Object.assign(new Error("'code' required"), { code: RPC_INVALID_P });
        const code = p.code.trim();
        if (code === "app.documents.length")           return ps().app.documents.length;
        if (code === "app.activeDocument.name")        return requireDoc().name;
        if (code === "app.activeDocument.layers.length") return requireDoc().layers.length;
        if (code === "app.activeDocument.width")       return requireDoc().width;
        if (code === "app.activeDocument.height")      return requireDoc().height;
        throw Object.assign(
            new Error(
                "Arbitrary new Function() is blocked by UXP CSP. " +
                "Use ps.executeAction with batchPlay, or built-in expressions."
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

    writeLog(`→ ${req.method} id=${req.id}`);
    try {
        const result = await handler(req.params || {});
        writeLog(`← ${req.method} OK`);
        return ok(req.id, result);
    } catch (e) {
        writeLog(`← ${req.method} ERROR ${e.code||RPC_INTERNAL}: ${e.message}`);
        return err(req.id, e.code || RPC_INTERNAL, e.message || String(e));
    }
}

// ── WebSocket client with exponential back-off ────────────────────────────────
const WS_URL = "ws://localhost:9001";
const RECONNECT_BASE = 3000;    // 3 s initial delay
const RECONNECT_MAX  = 60000;   // 60 s cap
let _ws            = null;
let _stopped       = false;
let _timer         = null;
let _onStatus      = null;
let _reconnectMs   = RECONNECT_BASE;  // current delay (grows with back-off)

function setStatus(s, d) {
    writeLog(s + (d ? ": " + d : ""));
    if (_onStatus) _onStatus(s, d);
}

function connect() {
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return;
    _stopped = false;
    setStatus("Connecting", WS_URL);
    try { _ws = new WebSocket(WS_URL); } catch(e) {
        setStatus("Disconnected", "Failed: " + e.message);
        schedRecon(); return;
    }
    _ws.onopen = () => {
        _reconnectMs = RECONNECT_BASE;  // reset back-off on success
        setStatus("Connected", "Bridge connected at " + WS_URL);
        _ws.send(JSON.stringify({ type:"hello", client:"photoshop-uxp", version:"0.1.0" }));
    };
    _ws.onmessage = async (ev) => {
        const raw  = typeof ev.data === "string" ? ev.data : String(ev.data);
        const resp = await dispatch(raw);
        if (resp && _ws && _ws.readyState === WebSocket.OPEN) _ws.send(resp);
    };
    _ws.onerror = (e) => setStatus("Error", String(e.message || e));
    _ws.onclose = (e) => {
        _ws = null;
        if (!_stopped) {
            setStatus("Disconnected", `Code ${e.code} — retry in ${(_reconnectMs/1000).toFixed(0)}s…`);
            schedRecon();
        } else {
            setStatus("Disconnected", "Stopped");
        }
    };
}

function schedRecon() {
    if (_timer) return;
    _timer = setTimeout(() => {
        _timer = null;
        if (!_stopped) {
            // Double the delay for next failure, capped at max
            _reconnectMs = Math.min(_reconnectMs * 2, RECONNECT_MAX);
            connect();
        }
    }, _reconnectMs);
}

function disconnect() {
    _stopped = true;
    if (_timer) { clearTimeout(_timer); _timer = null; }
    if (_ws)    { _ws.close(); _ws = null; }
    _reconnectMs = RECONNECT_BASE;
    setStatus("Disconnected", "Stopped by user");
}

// ── Panel UI ──────────────────────────────────────────────────────────────────
const statusEl = document.getElementById("status");
const logEl    = document.getElementById("log");
const btnC     = document.getElementById("btn-connect");
const btnD     = document.getElementById("btn-disconnect");
const logPathEl = document.getElementById("log-path");

function addLog(t) {
    if (!logEl) return;
    const d = document.createElement("div");
    d.className   = "log-line";
    d.textContent = "[" + new Date().toLocaleTimeString() + "] " + t;
    logEl.insertBefore(d, logEl.firstChild);
    while (logEl.children.length > 50) logEl.removeChild(logEl.lastChild);
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

// Init log file, then start connection
initLogFile().then(() => {
    if (logPathEl && _logFile) {
        try { logPathEl.textContent = "Log: " + _logFile.nativePath; } catch(_) {}
    }
    connect();
});
