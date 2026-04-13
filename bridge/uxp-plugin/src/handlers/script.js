/**
 * JSON-RPC handlers for executing arbitrary Photoshop scripts.
 *
 * Methods exposed:
 *   ps.executeScript     — evaluate a JavaScript expression via batchPlay
 *   ps.executeAction     — run a Photoshop Action (from the Actions panel)
 */

"use strict";

const photoshop = require("photoshop");

/**
 * ps.executeScript — evaluate a JavaScript expression in the Photoshop context.
 *
 * The code is wrapped in an async function and executed via batchPlay.
 * Supports any expression that returns a JSON-serialisable value.
 *
 * @param {object} params
 * @param {string} params.code - JavaScript code to evaluate.
 * @returns {*} Return value of the script (must be JSON-serialisable).
 *
 * Example::
 *
 *   bridge.call("ps.executeScript", code="app.documents.length")
 *   bridge.call("ps.executeScript", code="app.activeDocument.name")
 */
async function executeScript(params) {
    const { code } = params;
    if (!code) throw Object.assign(new Error("'code' parameter is required"), { code: -32602 });

    // Use photoshop.core.executeAsModal to get write access when needed
    let result;
    try {
        result = await photoshop.core.executeAsModal(
            async () => {
                // eslint-disable-next-line no-new-func
                const fn = new Function(`return (async () => { return (${code}); })()`);
                return await fn();
            },
            { commandName: "executeScript" }
        );
    } catch (e) {
        // Fallback: try direct eval for read-only scripts
        try {
            // eslint-disable-next-line no-new-func
            const fn = new Function(`return (async () => { return (${code}); })()`);
            result = await fn();
        } catch (e2) {
            throw Object.assign(
                new Error(`Script execution failed: ${e2.message}`),
                { code: -32603 }
            );
        }
    }

    // Ensure result is JSON-serialisable
    try {
        JSON.stringify(result);
        return result;
    } catch (_e) {
        return String(result);
    }
}

/**
 * ps.executeAction — run a named Photoshop Action from the Actions panel.
 * @param {object} params
 * @param {string} params.action - Action name.
 * @param {string} params.action_set - Action set (group) name.
 */
async function executeAction(params) {
    const { action, action_set } = params;
    if (!action) throw Object.assign(new Error("'action' parameter is required"), { code: -32602 });
    if (!action_set) throw Object.assign(new Error("'action_set' parameter is required"), { code: -32602 });

    await photoshop.core.executeAsModal(
        async () => {
            await photoshop.action.batchPlay(
                [
                    {
                        _obj: "play",
                        _target: [{ _ref: "action", _name: action }],
                        using: { _ref: "actionSet", _name: action_set },
                    },
                ],
                {}
            );
        },
        { commandName: `Run action: ${action_set}/${action}` }
    );

    return { executed: true, action, action_set };
}

module.exports = {
    "ps.executeScript": executeScript,
    "ps.executeAction": executeAction,
};
