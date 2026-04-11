"""Basic tests for PhotoshopMcpServer and bridge (without real Photoshop)."""

from __future__ import annotations

import pytest


def test_import():
    """Package imports without errors."""
    import dcc_mcp_photoshop

    assert dcc_mcp_photoshop.__version__ == "0.1.0"


def test_api_imports():
    """All public API symbols are importable."""
    from dcc_mcp_photoshop import (
        PhotoshopBridge,
        PhotoshopMcpServer,
        is_photoshop_available,
        ps_error,
        ps_from_exception,
        ps_success,
        start_server,
        stop_server,
        with_photoshop,
    )

    assert callable(PhotoshopMcpServer)
    assert callable(PhotoshopBridge)
    assert callable(ps_success)
    assert callable(ps_error)
    assert callable(ps_from_exception)
    assert callable(is_photoshop_available)
    assert callable(start_server)
    assert callable(stop_server)
    assert callable(with_photoshop)


def test_is_photoshop_available_false_when_bridge_disconnected():
    """is_photoshop_available() is False when bridge is not connected."""
    from dcc_mcp_photoshop import is_photoshop_available

    assert is_photoshop_available() is False


def test_ps_success_returns_dict():
    """ps_success() returns a dict with expected keys."""
    from dcc_mcp_photoshop import ps_success

    result = ps_success("test done", layer_count=5)
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert result.get("message") == "test done"


def test_ps_success_with_context():
    """ps_success() stores context kwargs."""
    from dcc_mcp_photoshop import ps_success

    result = ps_success("ok", width=1920, height=1080, color_mode="RGB")
    assert result.get("success") is True
    ctx = result.get("context", {})
    assert ctx.get("width") == 1920
    assert ctx.get("height") == 1080
    assert ctx.get("color_mode") == "RGB"


def test_ps_error_returns_failure_dict():
    """ps_error() returns a failure dict."""
    from dcc_mcp_photoshop import ps_error

    result = ps_error("failed", error="ConnectionError: bridge not connected")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert result.get("error") == "ConnectionError: bridge not connected"


def test_ps_from_exception():
    """ps_from_exception() captures exception info."""
    from dcc_mcp_photoshop import ps_from_exception

    try:
        raise ValueError("test error")
    except ValueError as exc:
        result = ps_from_exception(exc, "Something went wrong")

    assert result.get("success") is False
    assert "Something went wrong" in result.get("message", "")


def test_bridge_not_connected_raises():
    """get_bridge() raises PhotoshopNotAvailableError when not connected."""
    from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, get_bridge

    with pytest.raises(PhotoshopNotAvailableError):
        get_bridge()


def test_bridge_call_raises_not_implemented():
    """PhotoshopBridge.call() raises NotImplementedError (placeholder)."""
    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    bridge = PhotoshopBridge()
    bridge._connected = True  # simulate connected state
    with pytest.raises(NotImplementedError):
        bridge.call("ps.test")


def test_bridge_endpoint_format():
    """PhotoshopBridge.endpoint returns correct WebSocket URL."""
    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    bridge = PhotoshopBridge(host="localhost", port=3000)
    assert bridge.endpoint == "ws://localhost:3000"

    bridge2 = PhotoshopBridge(host="127.0.0.1", port=4000)
    assert bridge2.endpoint == "ws://127.0.0.1:4000"


def test_bridge_connect_disconnect():
    """PhotoshopBridge connect/disconnect toggles is_connected."""
    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    bridge = PhotoshopBridge()
    assert bridge.is_connected() is False
    bridge.connect()
    assert bridge.is_connected() is True
    bridge.disconnect()
    assert bridge.is_connected() is False


def test_bridge_context_manager():
    """PhotoshopBridge works as a context manager."""
    from dcc_mcp_photoshop.bridge import PhotoshopBridge

    bridge = PhotoshopBridge()
    with bridge:
        assert bridge.is_connected() is True
    assert bridge.is_connected() is False


def test_server_instantiation():
    """PhotoshopMcpServer can be instantiated with custom ports."""
    from dcc_mcp_photoshop import PhotoshopMcpServer

    server = PhotoshopMcpServer(port=9999, ws_port=4000)
    assert server._port == 9999
    assert server._ws_port == 4000


def test_with_photoshop_catches_not_available():
    """@with_photoshop catches PhotoshopNotAvailableError."""
    from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, with_photoshop
    from dcc_mcp_photoshop.api import ps_success

    @with_photoshop
    def needs_ps(**kwargs):
        raise PhotoshopNotAvailableError("not connected")

    result = needs_ps()
    assert result.get("success") is False
    assert "not available" in result.get("message", "").lower()


def test_with_photoshop_catches_general_exception():
    """@with_photoshop catches general Exception."""
    from dcc_mcp_photoshop.api import with_photoshop

    @with_photoshop
    def raises(**kwargs):
        raise RuntimeError("unexpected error")

    result = raises()
    assert result.get("success") is False
