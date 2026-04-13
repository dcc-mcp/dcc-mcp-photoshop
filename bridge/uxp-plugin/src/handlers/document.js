/**
 * JSON-RPC handlers for Photoshop document operations.
 *
 * Methods exposed:
 *   ps.getDocumentInfo    — active document metadata
 *   ps.listDocuments      — all open documents
 *   ps.openDocument       — open a file by path
 *   ps.saveDocument       — save the active document
 *   ps.closeDocument      — close the active document
 *   ps.exportDocument     — export to PNG / JPEG / PSD / TIFF
 */

"use strict";

const photoshop = require("photoshop");
const { requireActiveDocument, serializeDocument } = require("../utils/ps-helpers");

/**
 * ps.getDocumentInfo — return metadata for the active document.
 */
async function getDocumentInfo(_params) {
    const doc = requireActiveDocument();
    return serializeDocument(doc);
}

/**
 * ps.listDocuments — return all open documents.
 */
async function listDocuments(_params) {
    return Array.from(photoshop.app.documents).map(serializeDocument);
}

/**
 * ps.openDocument — open a file by absolute path.
 * @param {object} params
 * @param {string} params.path - Absolute path to the file.
 */
async function openDocument(params) {
    const { path } = params;
    if (!path) throw Object.assign(new Error("'path' parameter is required"), { code: -32602 });

    const { localFileSystem } = require("uxp").storage;
    const entry = await localFileSystem.getEntryWithUrl(`file:${path}`);
    const doc = await photoshop.app.open(entry);
    return serializeDocument(doc);
}

/**
 * ps.saveDocument — save the active document in its current format.
 */
async function saveDocument(_params) {
    const doc = requireActiveDocument();
    await doc.save();
    return { saved: true, path: doc.path || null };
}

/**
 * ps.closeDocument — close the active document.
 * @param {object} params
 * @param {boolean} [params.save=false] - Whether to save before closing.
 */
async function closeDocument(params) {
    const doc = requireActiveDocument();
    const save = params.save === true;
    await doc.close(save
        ? photoshop.constants.SaveOptions.SAVECHANGES
        : photoshop.constants.SaveOptions.DONOTSAVECHANGES
    );
    return { closed: true };
}

/**
 * ps.exportDocument — export the active document to a file.
 * @param {object} params
 * @param {string} params.path - Output file path (absolute).
 * @param {string} [params.format="png"] - "png" | "jpg" | "tiff" | "psd"
 * @param {number} [params.quality=90] - JPEG quality (0-100, only for jpg).
 */
async function exportDocument(params) {
    const { path, format = "png", quality = 90 } = params;
    if (!path) throw Object.assign(new Error("'path' parameter is required"), { code: -32602 });

    const doc = requireActiveDocument();
    const { localFileSystem } = require("uxp").storage;

    // Ensure parent directory exists (best-effort)
    const pathParts = path.replace(/\\/g, "/").split("/");
    const fileName = pathParts.pop();
    const parentPath = pathParts.join("/");

    const parentFolder = await localFileSystem.getEntryWithUrl(`file:${parentPath}`);
    const outputFile = await parentFolder.createFile(fileName, { overwrite: true });

    const fmt = format.toLowerCase();
    if (fmt === "jpg" || fmt === "jpeg") {
        await doc.saveAs.jpg(outputFile, { quality: Math.min(100, Math.max(0, quality)) });
    } else if (fmt === "png") {
        await doc.saveAs.png(outputFile, { compression: 6 });
    } else if (fmt === "tiff" || fmt === "tif") {
        await doc.saveAs.tiff(outputFile, {});
    } else if (fmt === "psd") {
        await doc.saveAs.psd(outputFile, {});
    } else {
        throw Object.assign(
            new Error(`Unsupported format: ${format}. Use png, jpg, tiff, or psd.`),
            { code: -32602 }
        );
    }

    return { exported: true, path, format: fmt };
}

module.exports = {
    "ps.getDocumentInfo": getDocumentInfo,
    "ps.listDocuments": listDocuments,
    "ps.openDocument": openDocument,
    "ps.saveDocument": saveDocument,
    "ps.closeDocument": closeDocument,
    "ps.exportDocument": exportDocument,
};
