"""Basic tests for PhotoshopMcpServer (without real Photoshop)."""
from __future__ import annotations

import pytest


def test_import():
    import dcc_mcp_photoshop

    assert dcc_mcp_photoshop.__version__ == "0.1.0"


def test_api_imports():
    from dcc_mcp_photoshop import (
        PhotoshopBridge,
        PhotoshopMcpServer,
        is_photoshop_available,
        ps_error,
        ps_success,
        start_server,
        stop_server,
    )

    assert callable(PhotoshopMcpServer)
    assert callable(PhotoshopBridge)
    assert callable(ps_success)
    assert callable(ps_error)
    assert callable(is_photoshop_available)


def test_is_photoshop_available_false_when_bridge_disconnected():
    from dcc_mcp_photoshop import is_photoshop_available

    assert is_photoshop_available() is False


def test_ps_success():
    from dcc_mcp_photoshop import ps_success

    r = ps_success("done", layer_count=5)
    assert r["success"] is True
    assert r["message"] == "done"


def test_ps_error():
    from dcc_mcp_photoshop import ps_error

    r = ps_error("failed", error="ConnectionError: bridge not connected")
    assert r["success"] is False


def test_bridge_not_connected_raises():
    from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, get_bridge

    with pytest.raises(PhotoshopNotAvailableError):
        get_bridge()


def test_bridge_call_raises_when_not_connected():
    from dcc_mcp_photoshop.bridge import BridgeConnectionError, PhotoshopBridge

    bridge = PhotoshopBridge()
    # _connected=False, _loop=None — should raise BridgeConnectionError
    with pytest.raises(BridgeConnectionError):
        bridge.call("ps.test")
