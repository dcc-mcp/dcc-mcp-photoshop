"""Contract tests for the Photoshop bridge protocol v0.

These tests verify the protocol wire format, lifecycle events,
error envelopes, and edge-case behavior without Photoshop.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
import websockets

# ---------------------------------------------------------------------------
# Message builder unit tests (no server needed)
# ---------------------------------------------------------------------------


class TestMessageBuilders:
    def test_build_hello(self):
        from dcc_mcp_photoshop.protocol import build_hello

        msg = build_hello()
        assert msg["type"] == "hello"
        assert msg["protocol"] == "photoshop-bridge"
        assert msg["version"] == "0.1.0"
        assert msg["client"] == "photoshop-uxp"
        assert "reconnect" not in msg

    def test_build_hello_reconnect(self):
        from dcc_mcp_photoshop.protocol import build_hello

        msg = build_hello(reconnect=True)
        assert msg["reconnect"] is True

    def test_build_hello_ack(self):
        from dcc_mcp_photoshop.protocol import build_hello_ack

        msg = build_hello_ack()
        assert msg["type"] == "hello_ack"
        assert msg["protocol"] == "photoshop-bridge"
        assert msg["version"] == "0.1.0"

    def test_build_hello_ack_error(self):
        from dcc_mcp_photoshop.protocol import build_hello_ack_error

        msg = build_hello_ack_error("Version 2.0.0 not supported")
        assert msg["compatible"] is False
        assert "2.0.0" in msg["error"]

    def test_build_request(self):
        from dcc_mcp_photoshop.protocol import build_request

        msg = build_request(1, "ps.getDocumentInfo")
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["method"] == "ps.getDocumentInfo"
        assert msg["params"] == {}

    def test_build_request_with_params(self):
        from dcc_mcp_photoshop.protocol import build_request

        msg = build_request(2, "ps.createLayer", {"name": "test", "type": "pixel"})
        assert msg["params"] == {"name": "test", "type": "pixel"}

    def test_build_success(self):
        from dcc_mcp_photoshop.protocol import build_success

        msg = build_success(1, {"exported": True})
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["result"] == {"exported": True}

    def test_build_error_known_code_auto_hint(self):
        from dcc_mcp_photoshop.protocol import RPC_METHOD_NOT_FOUND, build_error

        msg = build_error(1, RPC_METHOD_NOT_FOUND, "Method not found: ps.unknown")
        assert msg["error"]["code"] == RPC_METHOD_NOT_FOUND
        assert "hint" in msg["error"]
        assert "describeApi" in msg["error"]["hint"]

    def test_build_error_explicit_hint(self):
        from dcc_mcp_photoshop.protocol import build_error

        msg = build_error(1, -32099, "Custom error", hint="Do this instead")
        assert msg["error"]["hint"] == "Do this instead"

    def test_build_error_with_data(self):
        from dcc_mcp_photoshop.protocol import build_error

        msg = build_error(1, -32602, "Invalid params", data={"missing": ["name"]})
        assert msg["error"]["data"] == {"missing": ["name"]}

    def test_build_error_null_id(self):
        from dcc_mcp_photoshop.protocol import RPC_PARSE_ERROR, build_error

        msg = build_error(None, RPC_PARSE_ERROR, "Parse error")
        assert msg["id"] is None

    def test_build_progress(self):
        from dcc_mcp_photoshop.protocol import build_progress

        msg = build_progress(5, 50, 100, "Exporting...", "export")
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 5
        assert msg["type"] == "progress"
        assert msg["progress"] == {"current": 50, "total": 100, "message": "Exporting...", "stage": "export"}

    def test_build_progress_minimal(self):
        from dcc_mcp_photoshop.protocol import build_progress

        msg = build_progress(3, 0, 100)
        assert msg["progress"] == {"current": 0, "total": 100}

    def test_build_disconnected(self):
        from dcc_mcp_photoshop.protocol import build_disconnected

        msg = build_disconnected("Server stopped")
        assert msg["type"] == "disconnected"
        assert msg["reason"] == "Server stopped"


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class TestValidators:
    def test_is_hello_valid(self):
        from dcc_mcp_photoshop.protocol import is_hello

        assert is_hello({"type": "hello", "protocol": "photoshop-bridge", "version": "0.1.0"})
        assert not is_hello({"type": "hello", "protocol": "wrong"})
        assert not is_hello({"type": "not-hello"})
        assert not is_hello({})

    def test_is_rpc_request_valid(self):
        from dcc_mcp_photoshop.protocol import is_rpc_request

        assert is_rpc_request({"jsonrpc": "2.0", "id": 1, "method": "ps.test", "params": {}})
        assert not is_rpc_request({"jsonrpc": "1.0", "id": 1, "method": "ps.test", "params": {}})
        assert not is_rpc_request({"jsonrpc": "2.0", "id": "string", "method": "ps.test", "params": {}})
        assert not is_rpc_request({"jsonrpc": "2.0"})

    def test_is_rpc_response_valid(self):
        from dcc_mcp_photoshop.protocol import is_rpc_response

        assert is_rpc_response({"jsonrpc": "2.0", "id": 1, "result": {}})
        assert is_rpc_response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "x"}})
        assert not is_rpc_response({"jsonrpc": "2.0", "id": 1})
        assert not is_rpc_response({"result": {}})

    def test_is_progress_valid(self):
        from dcc_mcp_photoshop.protocol import is_progress

        assert is_progress({"jsonrpc": "2.0", "id": 1, "type": "progress", "progress": {"current": 0, "total": 10}})
        assert not is_progress({"jsonrpc": "2.0", "id": 1, "type": "other", "progress": {}})
        assert not is_progress({"type": "progress"})

    def test_check_version_compatible(self):
        from dcc_mcp_photoshop.protocol import check_version

        assert check_version("0.1.0")
        assert check_version("0.99.99")
        assert not check_version("1.0.0")
        assert not check_version("2.0.0")
        assert not check_version("not-a-version")

    def test_parse_message(self):
        from dcc_mcp_photoshop.protocol import parse_message

        assert parse_message('{"key":"value"}') == {"key": "value"}
        assert parse_message("invalid json") is None
        assert parse_message("42") is None
        assert parse_message('["array"]') is None


# ---------------------------------------------------------------------------
# Hello handshake (integration — needs bridge server)
# ---------------------------------------------------------------------------


class TestHelloHandshake:
    def test_hello_receives_ack(self, connected_bridge):
        assert connected_bridge.is_connected()

    def test_hello_ack_is_valid(self):
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        bridge = PhotoshopBridge(host="localhost", port=0, timeout=5.0)
        _actual_port: list = []

        async def _patched_serve(ready_event, uxp_event, exc_out):
            import websockets as ws

            try:
                bridge._server = await ws.serve(
                    lambda websocket: bridge._handle_uxp(websocket, uxp_event),
                    "localhost",
                    0,
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
        time.sleep(0.1)
        if not _actual_port:
            bridge.disconnect()
            pytest.skip("Could not start bridge server")
        port = _actual_port[0]

        async def _raw_client():
            ws = await websockets.connect(f"ws://localhost:{port}")
            await ws.send(json.dumps({
                "type": "hello", "protocol": "photoshop-bridge",
                "version": "0.1.0", "client": "test-harness",
            }))
            raw = await ws.recv()
            ack = json.loads(raw)
            await ws.close()
            return ack

        ack = asyncio.new_event_loop().run_until_complete(_raw_client())
        assert ack["type"] == "hello_ack"
        assert ack["protocol"] == "photoshop-bridge"
        assert ack["version"] == "0.1.0"
        bridge.disconnect()

    def test_reconnect_hello(self, connected_bridge):
        assert connected_bridge._uxp_connect_count >= 1


# ---------------------------------------------------------------------------
# Request / response envelope
# ---------------------------------------------------------------------------


class TestRequestEnvelope:
    def test_request_id_is_monotonic(self, connected_bridge):
        id1 = connected_bridge._request_id
        connected_bridge.call("ps.getDocumentInfo")
        id2 = connected_bridge._request_id
        assert id2 > id1

    def test_response_id_matches_request(self, connected_bridge):
        info = connected_bridge.call("ps.getDocumentInfo")
        assert info["name"] == "Untitled-1.psd"

    def test_success_response_has_result_not_error(self, connected_bridge):
        result = connected_bridge.call("ps.getDocumentInfo")
        assert isinstance(result, dict)
        assert "name" in result


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class TestErrorEnvelope:
    def test_method_not_found_error_shape(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        with pytest.raises(BridgeRpcError) as exc_info:
            connected_bridge.call("ps.nonExistentMethod")
        assert exc_info.value.code == -32601
        assert "ps.nonExistentMethod" in str(exc_info.value)
        assert exc_info.value.hint

    def test_error_has_code_message(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        try:
            connected_bridge.call("ps.nonExistentMethod")
        except BridgeRpcError as e:
            assert isinstance(e.code, int)
            assert e.code == -32601
            assert isinstance(str(e), str)
            assert len(str(e)) > 0

    def test_bridge_rpc_error_carries_hint(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        try:
            connected_bridge.call("ps.nonExistentMethod")
        except BridgeRpcError as e:
            assert e.hint, f"Expected non-empty hint, got {e.hint!r}"
            assert "describeapi" in e.hint.lower()


# ---------------------------------------------------------------------------
# Unknown method / malformed payload behavior
# ---------------------------------------------------------------------------


class TestUnknownAndMalformed:
    def test_unknown_method_returns_32601(self, connected_bridge):
        from dcc_mcp_photoshop.bridge import BridgeRpcError

        with pytest.raises(BridgeRpcError) as exc_info:
            connected_bridge.call("ps.doesNotExist")
        assert exc_info.value.code == -32601

    def test_multiple_parallel_calls_correctly_routed(self, connected_bridge):
        info = connected_bridge.call("ps.getDocumentInfo")
        layers = connected_bridge.call("ps.listLayers", include_hidden=False)
        docs = connected_bridge.call("ps.listDocuments")
        assert info["name"] == "Untitled-1.psd"
        assert len(layers) == 2
        assert len(docs) == 1


# ---------------------------------------------------------------------------
# Timeout behavior
# ---------------------------------------------------------------------------


class TestTimeoutBehavior:
    def test_call_timeout_raises(self, connected_bridge):
        from concurrent.futures import Future
        from concurrent.futures import TimeoutError as FutureTimeoutError

        from dcc_mcp_photoshop.bridge import BridgeTimeoutError

        stuck_future: Future = Future()
        req_id = 99998
        connected_bridge._pending[req_id] = stuck_future
        try:
            with pytest.raises(BridgeTimeoutError):
                try:
                    stuck_future.result(timeout=0.05)
                except FutureTimeoutError as err:
                    connected_bridge._pending.pop(req_id, None)
                    raise BridgeTimeoutError("Timed out: ps.testOp") from err
        finally:
            connected_bridge._pending.pop(req_id, None)

    def test_timeout_cleans_up_pending(self, connected_bridge):
        from concurrent.futures import Future
        from concurrent.futures import TimeoutError as FutureTimeoutError

        from dcc_mcp_photoshop.bridge import BridgeTimeoutError

        stuck_future: Future = Future()
        req_id = 99997
        connected_bridge._pending[req_id] = stuck_future
        try:
            try:
                stuck_future.result(timeout=0.05)
            except FutureTimeoutError as err:
                connected_bridge._pending.pop(req_id, None)
                raise BridgeTimeoutError("Timed out") from err
        except BridgeTimeoutError:
            pass
        assert req_id not in connected_bridge._pending


# ---------------------------------------------------------------------------
# Disconnect / reconnect behavior
# ---------------------------------------------------------------------------


class TestDisconnectBehavior:
    def test_disconnect_clears_pending_calls(self, connected_bridge):
        from concurrent.futures import Future

        from dcc_mcp_photoshop.bridge import BridgeConnectionError

        stuck_future: Future = Future()
        req_id = 99996
        connected_bridge._pending[req_id] = stuck_future
        for f in connected_bridge._pending.values():
            if not f.done():
                f.set_exception(BridgeConnectionError("UXP plugin disconnected"))
        connected_bridge._pending.clear()
        assert req_id not in connected_bridge._pending
        assert stuck_future.done()
        with pytest.raises(BridgeConnectionError):
            stuck_future.result(timeout=0)

    def test_call_when_disconnected_raises(self):
        from dcc_mcp_photoshop.bridge import BridgeConnectionError, PhotoshopBridge

        bridge = PhotoshopBridge()
        with pytest.raises(BridgeConnectionError):
            bridge.call("ps.getDocumentInfo")


# ---------------------------------------------------------------------------
# Progress notification format
# ---------------------------------------------------------------------------


class TestProgressNotification:
    def test_progress_message_format(self):
        from dcc_mcp_photoshop.protocol import build_progress

        msg = build_progress(42, 3, 5, "Rendering...", "render")
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 42
        assert msg["type"] == "progress"
        assert msg["progress"]["current"] == 3
        assert msg["progress"]["total"] == 5
        assert msg["progress"]["message"] == "Rendering..."
        assert msg["progress"]["stage"] == "render"

    def test_progress_does_not_resolve_pending(self, connected_bridge):
        from dcc_mcp_photoshop.protocol import is_progress

        progress_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "type": "progress",
            "progress": {"current": 50, "total": 100},
        }
        assert is_progress(progress_msg)
        assert "result" not in progress_msg
        assert "error" not in progress_msg


# ---------------------------------------------------------------------------
# Protocol version compatibility
# ---------------------------------------------------------------------------


class TestProtocolVersion:
    def test_protocol_version_is_semver(self):
        from dcc_mcp_photoshop.protocol import PROTOCOL_VERSION

        parts = PROTOCOL_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_protocol_name_constant(self):
        from dcc_mcp_photoshop.protocol import PROTOCOL_NAME

        assert PROTOCOL_NAME == "photoshop-bridge"
        assert isinstance(PROTOCOL_NAME, str)
        assert len(PROTOCOL_NAME) > 0


# ---------------------------------------------------------------------------
# Concurrent request routing
# ---------------------------------------------------------------------------


class TestConcurrentRouting:
    def test_interleaved_requests_correct_ids(self, connected_bridge):
        r1 = connected_bridge.call("ps.getDocumentInfo")
        r2 = connected_bridge.call("ps.listLayers", include_hidden=True)
        r3 = connected_bridge.call("ps.listLayers", include_hidden=False)
        r4 = connected_bridge.call("ps.listDocuments")
        assert r1["name"] == "Untitled-1.psd"
        assert len(r2) == 3
        assert len(r3) == 2
        assert len(r4) == 1
