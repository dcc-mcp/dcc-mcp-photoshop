"""Shared pytest fixtures for dcc-mcp-photoshop tests.

Architecture recap (Python = WS server, UXP = WS client):

    PhotoshopBridge (Python, WS server :port)
         ↑ connects
    mock_uxp_client  ←  simulates the UXP plugin

Key fixtures
------------
``connected_bridge``
    A ``PhotoshopBridge`` server running on a random port, with a mock UXP
    client already connected.  Automatically tears down after each test.

``mock_uxp_server`` (legacy alias)
    Yields ``(host, port)`` of the bridge server after mock UXP connects.
    Kept for backward compatibility with test_bridge.py.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict

import pytest

# ---------------------------------------------------------------------------
# Mock UXP handlers (realistic Photoshop response shapes)
# ---------------------------------------------------------------------------

MOCK_DOCUMENT = {
    "id": 1,
    "name": "Untitled-1.psd",
    "width": 1920,
    "height": 1080,
    "resolution": 72.0,
    "color_mode": "RGBColor",
    "bit_depth": 8,
    "path": None,
    "has_unsaved_changes": False,
}

MOCK_LAYERS = [
    {
        "id": 101,
        "name": "Background",
        "type": "pixel",
        "visible": True,
        "opacity": 100,
        "locked": True,
        "bounds": {"top": 0, "left": 0, "bottom": 1080, "right": 1920, "width": 1920, "height": 1080},
    },
    {
        "id": 102,
        "name": "Layer 1",
        "type": "pixel",
        "visible": True,
        "opacity": 75,
        "locked": False,
        "bounds": {"top": 100, "left": 100, "bottom": 500, "right": 500, "width": 400, "height": 400},
    },
    {
        "id": 103,
        "name": "Hidden Layer",
        "type": "pixel",
        "visible": False,
        "opacity": 100,
        "locked": False,
        "bounds": None,
    },
]


async def _handle_rpc(request: Dict[str, Any]) -> Any:
    """Dispatch a JSON-RPC request to the appropriate mock handler."""
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ps.getDocumentInfo":
        return MOCK_DOCUMENT
    if method == "ps.listDocuments":
        return [MOCK_DOCUMENT]
    if method == "ps.listLayers":
        include_hidden = params.get("include_hidden", True)
        return MOCK_LAYERS if include_hidden else [l for l in MOCK_LAYERS if l["visible"]]
    if method == "ps.executeScript":
        code = params.get("code", "")
        if code == "app.documents.length":
            return 1
        if code == "app.activeDocument.name":
            return MOCK_DOCUMENT["name"]
        return f"script_result:{code}"
    if method == "ps.createLayer":
        return {"id": 999, "name": params.get("name", "New Layer"), "type": params.get("type", "pixel")}
    if method == "ps.deleteLayer":
        return {"deleted": True, "name": params.get("name")}
    if method == "ps.setLayerVisibility":
        return {"name": params.get("name"), "visible": params.get("visible")}
    if method == "ps.renameLayer":
        return {"old_name": params.get("name"), "name": params.get("new_name")}
    if method == "ps.setLayerOpacity":
        return {"name": params.get("name"), "opacity": params.get("opacity")}
    if method == "ps.duplicateLayer":
        name = params.get("new_name") or f"{params.get('name')} copy"
        return {"id": 1000, "name": name}
    if method == "ps.saveDocument":
        return {"saved": True, "path": None}
    if method == "ps.closeDocument":
        return {"closed": True}
    if method == "ps.exportDocument":
        return {"exported": True, "path": params.get("path"), "format": params.get("format", "png")}
    if method == "ps.executeAction":
        return {"executed": True, "action": params.get("action"), "action_set": params.get("action_set")}

    # ── Image operations ────────────────────────────────────────────────
    if method == "ps.createDocument":
        return {
            "id": 2,
            "name": params.get("name", "Untitled"),
            "width": params.get("width", 1920),
            "height": params.get("height", 1080),
            "resolution": params.get("resolution", 72.0),
            "color_mode": params.get("color_mode", "rgb"),
            "bit_depth": params.get("bit_depth", 8),
            "path": None,
            "has_unsaved_changes": False,
        }
    if method == "ps.resizeCanvas":
        return {"width": params.get("width"), "height": params.get("height")}
    if method == "ps.resizeImage":
        return {"width": params.get("width"), "height": params.get("height")}
    if method == "ps.flattenImage":
        return {"flattened": True}
    if method == "ps.mergeVisibleLayers":
        return {"merged": True, "layer_name": "Merged"}

    # ── Layer extended ──────────────────────────────────────────────────
    if method == "ps.setLayerBlendMode":
        return {"name": params.get("name"), "blend_mode": params.get("blend_mode")}
    if method == "ps.fillLayer":
        return {"filled": True, "name": params.get("name"), "color": params.get("color")}

    # ── Text layers ─────────────────────────────────────────────────────
    if method == "ps.createTextLayer":
        return {
            "id": 998,
            "name": params.get("name", params.get("content", "")[:20]),
            "content": params.get("content"),
        }
    if method == "ps.updateTextLayer":
        return {"name": params.get("name"), "content": params.get("content")}
    if method == "ps.getTextLayerInfo":
        return {
            "name": params.get("name"),
            "content": "Hello, World!",
            "font": "ArialMT",
            "size": 48.0,
            "color": "#000000",
            "alignment": "left",
            "bold": False,
            "italic": False,
        }

    raise ValueError(f"Method not found: {method}")


# ---------------------------------------------------------------------------
# connected_bridge fixture
# ---------------------------------------------------------------------------
#
# New architecture: Python is the WS *server*, UXP is the WS *client*.
# The fixture:
#   1. Creates a PhotoshopBridge (starts Python WS server on random port).
#   2. Starts a mock "UXP client" that connects to that server.
#   3. The mock client reads RPC requests from Python and replies with mock data.
#   4. Yields the connected bridge.
# ---------------------------------------------------------------------------


@pytest.fixture()
def connected_bridge():
    """Return a PhotoshopBridge server with a mock UXP client connected.

    The mock UXP client answers all JSON-RPC calls with realistic mock data.
    """
    import websockets  # noqa: PLC0415

    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    # Start the bridge server on a random port
    bridge = PhotoshopBridge(host="localhost", port=0, timeout=10.0)

    # We need to know the actual port after the server starts — patch _serve
    # to use port 0 (OS assigns) and read back the real port.
    _actual_port: list = []

    original_serve = bridge._serve

    async def _patched_serve(ready_event, uxp_event, exc_out):
        import websockets as ws  # noqa: PLC0415

        try:
            bridge._server = await ws.serve(
                lambda websocket: bridge._handle_uxp(websocket, uxp_event),
                "localhost",
                0,  # OS assigns free port
            )
            port = bridge._server.sockets[0].getsockname()[1]
            _actual_port.append(port)
            bridge._port = port  # update for endpoint property
        except Exception as exc:
            exc_out.append(exc)
        finally:
            ready_event.set()

    bridge._serve = _patched_serve

    # Start the server
    bridge.connect(wait_for_uxp=False)

    # Give the server a moment to be ready
    import time
    for _ in range(20):
        if _actual_port:
            break
        time.sleep(0.05)

    if not _actual_port:
        bridge.disconnect()
        pytest.skip("Could not start bridge server")

    port = _actual_port[0]

    # Start the mock UXP client in a background thread
    uxp_loop = asyncio.new_event_loop()
    uxp_started = threading.Event()
    uxp_stop_event = asyncio.Event()

    async def _run_mock_uxp():
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            # Send hello
            await ws.send(json.dumps({
                "type": "hello", "client": "photoshop-uxp-mock", "version": "0.1.0"
            }))
            uxp_started.set()

            try:
                async for raw in ws:
                    try:
                        req = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    # Ignore non-RPC messages
                    if not req.get("method"):
                        continue

                    req_id = req.get("id")
                    try:
                        result = await _handle_rpc(req)
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}))
                    except ValueError as exc:
                        await ws.send(json.dumps({
                            "jsonrpc": "2.0", "id": req_id,
                            "error": {"code": -32601, "message": str(exc)},
                        }))
                    except Exception as exc:  # noqa: BLE001
                        await ws.send(json.dumps({
                            "jsonrpc": "2.0", "id": req_id,
                            "error": {"code": -32603, "message": str(exc)},
                        }))
            except Exception:
                pass

    def _uxp_thread():
        asyncio.set_event_loop(uxp_loop)
        try:
            uxp_loop.run_until_complete(_run_mock_uxp())
        except Exception:
            pass
        finally:
            uxp_loop.close()

    t = threading.Thread(target=_uxp_thread, daemon=True, name="mock-uxp-client")
    t.start()

    # Wait for mock UXP to connect and bridge to see it
    uxp_started.wait(timeout=5)
    for _ in range(50):
        if bridge.is_connected():
            break
        time.sleep(0.05)

    if not bridge.is_connected():
        bridge.disconnect()
        t.join(timeout=2)
        pytest.skip("Mock UXP client did not connect in time")

    yield bridge

    bridge.disconnect()
    t.join(timeout=3)


@pytest.fixture()
def mock_uxp_server(connected_bridge):
    """Legacy alias: yield (host, port) of the connected bridge server.

    Tests that use ``mock_uxp_server`` and create their own bridge can use
    this to get the server address.
    """
    yield (connected_bridge._host, connected_bridge._port)
