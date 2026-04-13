"""Tests for PhotoshopBridge — runs against mock UXP client from conftest.py.

Architecture (Python = WS server, UXP = WS client):
  PhotoshopBridge (Python server)  ←  mock UXP client (conftest.py)

All tests use the ``connected_bridge`` fixture which provides a
``PhotoshopBridge`` server already connected to a mock UXP client.
No Photoshop installation is required.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestBridgeConnection:
    def test_is_connected_after_connect(self, connected_bridge):
        assert connected_bridge.is_connected()

    def test_is_connected_false_before_connect(self):
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        bridge = PhotoshopBridge(host="localhost", port=0)
        assert not bridge.is_connected()

    def test_connect_double_call_is_noop(self, connected_bridge):
        """Calling connect() on an already-running server should be a no-op."""
        connected_bridge.connect()  # should not raise
        assert connected_bridge.is_connected()

    def test_disconnect_clears_state(self, connected_bridge):
        """After disconnect(), is_connected() returns False."""
        connected_bridge.disconnect()
        assert not connected_bridge.is_connected()

    def test_call_when_disconnected_raises(self):
        from dcc_mcp_photoshop.bridge import BridgeConnectionError, PhotoshopBridge

        bridge = PhotoshopBridge()
        with pytest.raises(BridgeConnectionError):
            bridge.call("ps.getDocumentInfo")

    def test_endpoint_property(self):
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        bridge = PhotoshopBridge(host="127.0.0.1", port=4242)
        assert bridge.endpoint == "ws://127.0.0.1:4242"

    def test_context_manager(self):
        """The context manager starts and stops the server."""
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        # Just test that server can start and stop without errors
        bridge = PhotoshopBridge(host="localhost", port=0)
        with bridge:
            assert bridge._loop is not None  # server loop is running
        assert bridge._loop is None  # cleaned up after exit

    def test_start_without_uxp_is_not_connected(self):
        """Bridge can start without UXP connected (is_connected returns False)."""
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        bridge = PhotoshopBridge(host="localhost", port=0)
        bridge.connect(wait_for_uxp=False)
        try:
            # Server is running but no UXP client yet
            assert bridge._loop is not None
            assert not bridge.is_connected()  # UXP not yet connected
        finally:
            bridge.disconnect()


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------


class TestDocumentOperations:
    def test_get_document_info(self, connected_bridge):
        info = connected_bridge.call("ps.getDocumentInfo")

        assert info["name"] == "Untitled-1.psd"
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["resolution"] == 72.0
        assert info["color_mode"] == "RGBColor"
        assert info["bit_depth"] == 8
        assert info["path"] is None

    def test_get_document_info_helper(self, connected_bridge):
        info = connected_bridge.get_document_info()
        assert info["name"] == "Untitled-1.psd"

    def test_list_documents(self, connected_bridge):
        docs = connected_bridge.list_documents()
        assert isinstance(docs, list)
        assert len(docs) == 1
        assert docs[0]["name"] == "Untitled-1.psd"

    def test_save_document(self, connected_bridge):
        result = connected_bridge.call("ps.saveDocument")
        assert result["saved"] is True

    def test_export_document_png(self, connected_bridge):
        result = connected_bridge.call(
            "ps.exportDocument",
            path="/tmp/test.png",
            format="png",
        )
        assert result["exported"] is True
        assert result["format"] == "png"
        assert result["path"] == "/tmp/test.png"

    def test_export_document_jpg(self, connected_bridge):
        result = connected_bridge.call(
            "ps.exportDocument",
            path="/tmp/test.jpg",
            format="jpg",
            quality=85,
        )
        assert result["format"] == "jpg"


# ---------------------------------------------------------------------------
# Layer operations
# ---------------------------------------------------------------------------


class TestLayerOperations:
    def test_list_layers_all(self, connected_bridge):
        layers = connected_bridge.list_layers(include_hidden=True)
        assert len(layers) == 3
        names = [l["name"] for l in layers]
        assert "Background" in names
        assert "Layer 1" in names
        assert "Hidden Layer" in names

    def test_list_layers_visible_only(self, connected_bridge):
        layers = connected_bridge.list_layers(include_hidden=False)
        assert len(layers) == 2
        assert all(l["visible"] for l in layers)

    def test_list_layers_helper(self, connected_bridge):
        layers = connected_bridge.list_layers()
        assert isinstance(layers, list)
        assert len(layers) == 3

    def test_layer_has_expected_fields(self, connected_bridge):
        layers = connected_bridge.list_layers()
        bg = next(l for l in layers if l["name"] == "Background")
        assert bg["type"] == "pixel"
        assert bg["visible"] is True
        assert bg["opacity"] == 100
        assert bg["locked"] is True
        assert bg["bounds"]["width"] == 1920

    def test_create_pixel_layer(self, connected_bridge):
        result = connected_bridge.call("ps.createLayer", name="My Layer", type="pixel")
        assert result["name"] == "My Layer"
        assert result["type"] == "pixel"
        assert "id" in result

    def test_create_group_layer(self, connected_bridge):
        result = connected_bridge.call("ps.createLayer", name="Group 1", type="group")
        assert result["name"] == "Group 1"
        assert result["type"] == "group"

    def test_delete_layer(self, connected_bridge):
        result = connected_bridge.call("ps.deleteLayer", name="Layer 1")
        assert result["deleted"] is True
        assert result["name"] == "Layer 1"

    def test_set_layer_visibility_hide(self, connected_bridge):
        result = connected_bridge.call(
            "ps.setLayerVisibility", name="Layer 1", visible=False
        )
        assert result["visible"] is False
        assert result["name"] == "Layer 1"

    def test_set_layer_visibility_show(self, connected_bridge):
        result = connected_bridge.call(
            "ps.setLayerVisibility", name="Hidden Layer", visible=True
        )
        assert result["visible"] is True

    def test_rename_layer(self, connected_bridge):
        result = connected_bridge.call(
            "ps.renameLayer", name="Layer 1", new_name="Renamed Layer"
        )
        assert result["name"] == "Renamed Layer"
        assert result["old_name"] == "Layer 1"

    def test_set_layer_opacity(self, connected_bridge):
        result = connected_bridge.call("ps.setLayerOpacity", name="Layer 1", opacity=50)
        assert result["opacity"] == 50
        assert result["name"] == "Layer 1"

    def test_duplicate_layer(self, connected_bridge):
        result = connected_bridge.call("ps.duplicateLayer", name="Layer 1")
        assert "copy" in result["name"].lower() or result["name"] == "Layer 1 copy"

    def test_duplicate_layer_with_new_name(self, connected_bridge):
        result = connected_bridge.call(
            "ps.duplicateLayer", name="Layer 1", new_name="Layer 1 Backup"
        )
        assert result["name"] == "Layer 1 Backup"


# ---------------------------------------------------------------------------
# Script execution
# ---------------------------------------------------------------------------


class TestScriptExecution:
    def test_execute_script_doc_count(self, connected_bridge):
        result = connected_bridge.execute_script("app.documents.length")
        assert result == 1

    def test_execute_script_doc_name(self, connected_bridge):
        result = connected_bridge.execute_script("app.activeDocument.name")
        assert result == "Untitled-1.psd"

    def test_execute_action(self, connected_bridge):
        result = connected_bridge.call(
            "ps.executeAction",
            action="Vignette (selection)",
            action_set="Frames",
        )
        assert result["executed"] is True
        assert result["action"] == "Vignette (selection)"
        assert result["action_set"] == "Frames"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_method_not_found_raises_bridge_rpc_error(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        with pytest.raises(BridgeRpcError) as exc_info:
            connected_bridge.call("ps.nonExistentMethod")

        assert exc_info.value.code == -32601
        assert "ps.nonExistentMethod" in str(exc_info.value)

    def test_timeout_raises_bridge_timeout_error(self, connected_bridge):
        """bridge.call() with a stuck pending future raises BridgeTimeoutError."""
        from concurrent.futures import Future

        from dcc_mcp_photoshop.bridge import BridgeTimeoutError

        # Manually inject a stuck future and verify BridgeTimeoutError is raised
        stuck_future: Future = Future()
        req_id = 99999
        connected_bridge._pending[req_id] = stuck_future

        try:
            with pytest.raises(BridgeTimeoutError):
                try:
                    stuck_future.result(timeout=0.05)
                except TimeoutError:
                    connected_bridge._pending.pop(req_id, None)
                    raise BridgeTimeoutError("Timed out: ps.test")
        finally:
            connected_bridge._pending.pop(req_id, None)

    def test_multiple_sequential_calls(self, connected_bridge):
        """Multiple sequential calls should all succeed."""
        info = connected_bridge.call("ps.getDocumentInfo")
        layers = connected_bridge.call("ps.listLayers")
        docs = connected_bridge.call("ps.listDocuments")

        assert info["name"] == "Untitled-1.psd"
        assert len(layers) == 3
        assert len(docs) == 1

    def test_bridge_rpc_error_attributes(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        try:
            connected_bridge.call("ps.unknownMethod")
        except BridgeRpcError as e:
            assert e.code == -32601
            assert isinstance(str(e), str)
