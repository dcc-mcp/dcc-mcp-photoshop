/**
 * JSON-RPC handlers for Photoshop layer operations.
 *
 * Methods exposed:
 *   ps.listLayers         — list all layers (with optional hidden filter)
 *   ps.createLayer        — create a new pixel / group layer
 *   ps.deleteLayer        — delete a layer by name
 *   ps.setLayerVisibility — show or hide a layer
 *   ps.renameLayer        — rename a layer
 *   ps.setLayerOpacity    — set layer opacity (0-100)
 *   ps.duplicateLayer     — duplicate a layer
 */

"use strict";

const photoshop = require("photoshop");
const {
    requireActiveDocument,
    serializeLayerTree,
    findLayerByName,
} = require("../utils/ps-helpers");

/**
 * ps.listLayers — return the layer tree for the active document.
 * @param {object} params
 * @param {boolean} [params.include_hidden=true]
 */
async function listLayers(params) {
    const includeHidden = params.include_hidden !== false;
    const doc = requireActiveDocument();

    let layers = Array.from(doc.layers).map(serializeLayerTree);
    if (!includeHidden) {
        layers = layers.filter((l) => l.visible);
    }
    return layers;
}

/**
 * ps.createLayer — create a new layer in the active document.
 * @param {object} params
 * @param {string} [params.name="Layer"] - New layer name.
 * @param {string} [params.type="pixel"] - "pixel" or "group".
 */
async function createLayer(params) {
    const { name = "Layer", type = "pixel" } = params;
    const doc = requireActiveDocument();

    let layer;
    if (type === "group") {
        layer = await doc.createLayerGroup({ name });
    } else {
        layer = await doc.createLayer({ name });
    }
    return { id: layer.id, name: layer.name, type: String(layer.kind) };
}

/**
 * ps.deleteLayer — delete a layer by name.
 * @param {object} params
 * @param {string} params.name - Layer name.
 */
async function deleteLayer(params) {
    const { name } = params;
    if (!name) throw Object.assign(new Error("'name' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const layer = findLayerByName(doc, name);
    if (!layer) {
        throw Object.assign(
            new Error(`Layer "${name}" not found`),
            { code: -32001 }
        );
    }
    await layer.delete();
    return { deleted: true, name };
}

/**
 * ps.setLayerVisibility — show or hide a layer.
 * @param {object} params
 * @param {string} params.name - Layer name.
 * @param {boolean} params.visible - True to show, false to hide.
 */
async function setLayerVisibility(params) {
    const { name, visible } = params;
    if (!name) throw Object.assign(new Error("'name' parameter is required"), { code: -32602 });
    if (visible === undefined) throw Object.assign(new Error("'visible' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const layer = findLayerByName(doc, name);
    if (!layer) throw Object.assign(new Error(`Layer "${name}" not found`), { code: -32001 });

    layer.visible = Boolean(visible);
    return { name, visible: layer.visible };
}

/**
 * ps.renameLayer — rename a layer.
 * @param {object} params
 * @param {string} params.name - Current layer name.
 * @param {string} params.new_name - New layer name.
 */
async function renameLayer(params) {
    const { name, new_name } = params;
    if (!name) throw Object.assign(new Error("'name' parameter is required"), { code: -32602 });
    if (!new_name) throw Object.assign(new Error("'new_name' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const layer = findLayerByName(doc, name);
    if (!layer) throw Object.assign(new Error(`Layer "${name}" not found`), { code: -32001 });

    layer.name = new_name;
    return { old_name: name, name: layer.name };
}

/**
 * ps.setLayerOpacity — set the opacity of a layer (0-100).
 * @param {object} params
 * @param {string} params.name - Layer name.
 * @param {number} params.opacity - Opacity value 0-100.
 */
async function setLayerOpacity(params) {
    const { name, opacity } = params;
    if (!name) throw Object.assign(new Error("'name' parameter is required"), { code: -32602 });
    if (opacity === undefined) throw Object.assign(new Error("'opacity' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const layer = findLayerByName(doc, name);
    if (!layer) throw Object.assign(new Error(`Layer "${name}" not found`), { code: -32001 });

    layer.opacity = Math.min(100, Math.max(0, Number(opacity)));
    return { name, opacity: layer.opacity };
}

/**
 * ps.duplicateLayer — duplicate a layer.
 * @param {object} params
 * @param {string} params.name - Layer name to duplicate.
 * @param {string} [params.new_name] - Name for the duplicate (default: "<name> copy").
 */
async function duplicateLayer(params) {
    const { name, new_name } = params;
    if (!name) throw Object.assign(new Error("'name' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const layer = findLayerByName(doc, name);
    if (!layer) throw Object.assign(new Error(`Layer "${name}" not found`), { code: -32001 });

    const duplicate = await layer.duplicate();
    if (new_name) duplicate.name = new_name;
    return { id: duplicate.id, name: duplicate.name };
}

module.exports = {
    "ps.listLayers": listLayers,
    "ps.createLayer": createLayer,
    "ps.deleteLayer": deleteLayer,
    "ps.setLayerVisibility": setLayerVisibility,
    "ps.renameLayer": renameLayer,
    "ps.setLayerOpacity": setLayerOpacity,
    "ps.duplicateLayer": duplicateLayer,
};
