/**
 * Photoshop UXP API helper utilities.
 *
 * Wraps common patterns for safely accessing Photoshop objects and
 * converting UXP types to plain JSON-serialisable values.
 */

"use strict";

const photoshop = require("photoshop");

/**
 * Return the active document, or throw if none is open.
 * @returns {Document}
 */
function requireActiveDocument() {
    const doc = photoshop.app.activeDocument;
    if (!doc) {
        const err = new Error("No active document in Photoshop");
        err.code = -32001;  // custom: no document
        throw err;
    }
    return doc;
}

/**
 * Serialise a Photoshop Document to a plain dict.
 * @param {Document} doc
 * @returns {object}
 */
function serializeDocument(doc) {
    return {
        id: doc.id,
        name: doc.name,
        width: doc.width,
        height: doc.height,
        resolution: doc.resolution,
        color_mode: String(doc.mode),
        bit_depth: doc.bitsPerChannel,
        path: doc.path || null,
        has_unsaved_changes: doc.dirty,
    };
}

/**
 * Serialise a Photoshop Layer to a plain dict.
 * @param {Layer} layer
 * @returns {object}
 */
function serializeLayer(layer) {
    const bounds = layer.bounds;
    return {
        id: layer.id,
        name: layer.name,
        type: String(layer.kind),
        visible: layer.visible,
        opacity: layer.opacity,
        locked: layer.allLocked,
        bounds: bounds
            ? {
                top: bounds.top,
                left: bounds.left,
                bottom: bounds.bottom,
                right: bounds.right,
                width: bounds.width,
                height: bounds.height,
            }
            : null,
    };
}

/**
 * Recursively serialise a layer and its children (for groups).
 * @param {Layer} layer
 * @returns {object}
 */
function serializeLayerTree(layer) {
    const data = serializeLayer(layer);
    if (layer.layers && layer.layers.length > 0) {
        data.children = Array.from(layer.layers).map(serializeLayerTree);
    }
    return data;
}

/**
 * Find a layer by name in the active document (top-level only).
 * Returns null if not found.
 * @param {Document} doc
 * @param {string} name
 * @returns {Layer|null}
 */
function findLayerByName(doc, name) {
    for (const layer of doc.layers) {
        if (layer.name === name) return layer;
    }
    return null;
}

module.exports = {
    requireActiveDocument,
    serializeDocument,
    serializeLayer,
    serializeLayerTree,
    findLayerByName,
};
