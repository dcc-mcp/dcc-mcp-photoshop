"""Shared pytest fixtures for dcc-mcp-photoshop tests.

Two test paths:
1. Legacy bridge tests: use ``connected_bridge`` / ``mock_uxp_server`` with
   the old ``PhotoshopBridge`` WebSocket mock. Tests files that still use
   ``get_bridge()`` directly (bridge.py, server.py, backward-compatible API).

2. Adobepy facade tests: use ``fake_broker_client`` which replaces
   ``BrokerClient`` globally so that ``Photoshop()`` instances get a
   ``FakeClient`` that returns realistic mock data without a real broker
   or Photoshop installation.
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
        "id": 101, "name": "Background", "type": "pixel", "visible": True,
        "opacity": 100, "locked": True,
        "bounds": {"top": 0, "left": 0, "bottom": 1080, "right": 1920, "width": 1920, "height": 1080},
    },
    {
        "id": 102, "name": "Layer 1", "type": "pixel", "visible": True,
        "opacity": 75, "locked": False,
        "bounds": {"top": 100, "left": 100, "bottom": 500, "right": 500, "width": 400, "height": 400},
    },
    {
        "id": 103, "name": "Hidden Layer", "type": "pixel", "visible": False,
        "opacity": 100, "locked": False, "bounds": None,
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
        return MOCK_LAYERS if include_hidden else [lyr for lyr in MOCK_LAYERS if lyr["visible"]]
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
    if method == "ps.createDocument":
        return {
            "id": 2, "name": params.get("name", "Untitled"),
            "width": params.get("width", 1920), "height": params.get("height", 1080),
            "resolution": params.get("resolution", 72.0),
            "color_mode": params.get("color_mode", "rgb"),
            "bit_depth": params.get("bit_depth", 8),
            "path": None, "has_unsaved_changes": False,
        }
    if method == "ps.resizeCanvas":
        return {"width": params.get("width"), "height": params.get("height")}
    if method == "ps.resizeImage":
        return {"width": params.get("width"), "height": params.get("height")}
    if method == "ps.flattenImage":
        return {"flattened": True}
    if method == "ps.mergeVisibleLayers":
        return {"merged": True, "layer_name": "Merged"}
    if method == "ps.setLayerBlendMode":
        return {"name": params.get("name"), "blend_mode": params.get("blend_mode")}
    if method == "ps.fillLayer":
        return {"filled": True, "name": params.get("name"), "color": params.get("color")}
    if method == "ps.createTextLayer":
        return {"id": 998, "name": params.get("name", params.get("content", "")[:20]), "content": params.get("content")}
    if method == "ps.updateTextLayer":
        return {"name": params.get("name"), "content": params.get("content")}
    if method == "ps.getTextLayerInfo":
        return {
            "name": params.get("name"), "content": "Hello, World!", "font": "ArialMT",
            "size": 48.0, "color": "#000000", "alignment": "left",
            "bold": False, "italic": False,
        }

    raise ValueError(f"Method not found: {method}")


# ---------------------------------------------------------------------------
# connected_bridge fixture (legacy — for bridge.py / server.py tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
def connected_bridge():
    """Return a PhotoshopBridge server with a mock UXP client connected."""
    import websockets  # noqa: PLC0415

    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    bridge = PhotoshopBridge(host="localhost", port=0, timeout=10.0)

    _actual_port: list = []
    _original_serve = bridge._serve

    async def _patched_serve(ready_event, uxp_event, exc_out):
        import websockets as ws  # noqa: PLC0415
        try:
            bridge._server = await ws.serve(
                lambda websocket: bridge._handle_uxp(websocket, uxp_event),
                "localhost", 0,
            )
            port = bridge._server.sockets[0].getsockname()[1]
            _actual_port.append(port)
            bridge._port = port
        except Exception as exc:
            exc_out.append(exc)
        finally:
            ready_event.set()

    bridge._serve = _patched_serve
    bridge.connect(wait_for_uxp=False)

    import time
    for _ in range(20):
        if _actual_port:
            break
        time.sleep(0.05)

    if not _actual_port:
        bridge.disconnect()
        pytest.skip("Could not start bridge server")

    port = _actual_port[0]

    uxp_loop = asyncio.new_event_loop()
    uxp_started = threading.Event()

    async def _run_mock_uxp():
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            await ws.send(json.dumps({"type": "hello", "client": "photoshop-uxp-mock", "version": "0.1.0"}))
            uxp_started.set()
            try:
                async for raw in ws:
                    try:
                        req = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not req.get("method"):
                        continue
                    req_id = req.get("id")
                    try:
                        result = await _handle_rpc(req)
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}))
                    except ValueError as exc:
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": str(exc)}}))
                    except Exception as exc:  # noqa: BLE001
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(exc)}}))
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
    """Legacy alias: yield (host, port) of the connected bridge server."""
    yield (connected_bridge._host, connected_bridge._port)


# ---------------------------------------------------------------------------
# FakeClient — adobepy test double
# ---------------------------------------------------------------------------


class FakeClient:
    """Test double for ``adobe.core.client.BrokerClient``.

    Accepts the same constructor signature as BrokerClient so it can be
    used via monkey-patching without signature mismatches.
    """

    target = "default"

    def __init__(
        self,
        broker_url: str | None = None,
        token: str | None = None,
        target: str = "default",
        timeout: float = 30.0,
    ) -> None:
        self.broker_url = broker_url
        self.token = token
        self.target = target
        self.timeout = timeout

    def call(self, host: str, namespace: str, method: str, args=None, options=None, target: str | None = None) -> Any:
        args = list(args or [])

        if namespace == "document" and method == "getActive":
            return {"id": 1, "name": "Untitled-1.psd", "width": 1920, "height": 1080, "resolution": 72.0, "mode": "RGBColor", "typename": "Document"}

        if namespace == "document" and method == "getLayers":
            return [
                {"id": 101, "name": "Background", "kind": "pixel", "visible": True, "opacity": 100, "typename": "Layer"},
                {"id": 102, "name": "Layer 1", "kind": "pixel", "visible": True, "opacity": 75, "typename": "Layer"},
                {"id": 103, "name": "Hidden Layer", "kind": "pixel", "visible": False, "opacity": 100, "typename": "Layer"},
            ]

        if namespace == "document" and method == "getActiveLayers":
            return [
                {"id": 101, "name": "Background", "kind": "pixel", "visible": True, "opacity": 100, "typename": "Layer"},
                {"id": 102, "name": "Layer 1", "kind": "pixel", "visible": True, "opacity": 75, "typename": "Layer"},
                {"id": 103, "name": "Hidden Layer", "kind": "pixel", "visible": False, "opacity": 100, "typename": "Layer"},
            ]

        if namespace == "app" and method == "getDocuments":
            return [{"id": 1, "name": "Untitled-1.psd", "width": 1920, "height": 1080}]

        if namespace == "app" and method == "getVersion":
            return "25.0.0"

        if namespace == "action" and method == "batchPlay":
            # Parse descriptors to return realistic responses
            descriptors = args[0] if args else []
            if isinstance(descriptors, list) and descriptors:
                desc = descriptors[0]
                obj = desc.get("_obj", "")
                target_ref = None
                target_list = desc.get("_target", [])
                if target_list:
                    target_ref = target_list[0].get("_ref", "")
                desc_name = desc.get("name", "New Layer")

                if obj == "make":
                    if target_ref == "textLayer":
                        using = desc.get("using", {})
                        content = using.get("textKey", "Text")
                        font = using.get("fontName", "ArialMT")
                        font_size = using.get("fontSize", {}).get("_value", 48)
                        color_obj = using.get("color", {})
                        color = "#000000"
                        if color_obj:
                            r = color_obj.get("red", 0)
                            g = color_obj.get("green", 0)
                            b = color_obj.get("blue", 0)
                            color = f"#{r:02x}{g:02x}{b:02x}"
                        return [{"id": 998, "name": desc_name or content[:20], "content": content, "fontName": font, "fontSize": font_size, "color": color}]
                    elif target_ref == "layerSection":
                        return [{"id": 999, "name": desc_name, "type": "group"}]
                    elif target_ref == "document":
                        using = desc.get("using", {})
                        return [{"id": 2, "name": using.get("name", "Untitled"), "width": using.get("width", {}).get("_value", 1920)}]
                    else:
                        return [{"id": 999, "name": desc_name, "type": "pixel"}]
                elif obj == "duplicate":
                    new_name = desc.get("name", "")
                    src_name = target_list[0].get("_name", "Layer") if target_list else "Layer"
                    return [{"id": 1000, "name": new_name or f"{src_name} copy"}]

            return [{"ok": True, "id": 999, "name": "New Layer"}]

        if namespace == "layer" and method == "getActive":
            return {"id": 102, "name": "Layer 1", "kind": "pixel", "visible": True, "opacity": 75}

        if namespace == "text" and method == "getActive":
            return {"layerId": 200, "contents": "Hello, World!", "font": "ArialMT", "size": 48.0}

        if namespace == "text" and method == "getByLayerId":
            return {"layerId": args[0] if args else 200, "contents": "Hello, World!", "font": "ArialMT", "size": 48.0}

        if namespace == "text" and method == "setContents":
            return {"layerId": args[0] if args else 200, "contents": args[1] if len(args) > 1 else "updated"}

        if namespace == "text" and method == "setCharacterStyle":
            return {"layerId": args[0] if args else 200, "contents": "Hello, World!"}

        if namespace == "document" and method == "export":
            path = args[0].get("path") if args else "output.png"
            return {"exported": True, "path": path}

        if namespace == "document" and method == "saveAs":
            return {"saved": True}

        if namespace == "export" and method == "getPresets":
            return []

        if namespace == "raw" and method == "evalJs":
            return "script_result"

        if namespace == "raw" and method == "getPath":
            return {}

        if namespace == "raw" and method == "callPath":
            return {}

        return {"ok": True}

    def capabilities(self) -> list[dict[str, Any]]:
        return []


@pytest.fixture(autouse=False)
def fake_broker_client(monkeypatch):
    """Replace BrokerClient with FakeClient globally.

    Use in tests that exercise migrated skill scripts with the adobepy facade.
    """
    import adobe.core as core_mod
    import adobe.core.client as client_mod
    import adobe.core.session as session_mod
    import adobe.photoshop.session as ps_session_mod

    monkeypatch.setattr(client_mod, "BrokerClient", FakeClient)
    monkeypatch.setattr(session_mod, "BrokerClient", FakeClient)
    monkeypatch.setattr(ps_session_mod, "BrokerClient", FakeClient)
    monkeypatch.setattr(core_mod, "BrokerClient", FakeClient)
    yield FakeClient
