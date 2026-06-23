"""Basic tests for PhotoshopMcpServer (without real Photoshop)."""

from __future__ import annotations

import pytest


def test_import():
    import dcc_mcp_photoshop

    assert dcc_mcp_photoshop.__version__ == "0.1.23"


def test_api_imports():
    from dcc_mcp_photoshop import (
        PhotoshopBridge,
        PhotoshopMcpServer,
        is_photoshop_available,
        ps_error,
        ps_success,
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


def test_run_daemon_uses_photoshop_config_for_broker_url(monkeypatch):
    import dcc_mcp_photoshop.server as server_mod

    seen = {}

    class FakeHandle:
        pass

    class FakeServer:
        is_running = False

        def __init__(self, *, config, port, server_name, gateway_port):
            seen["config"] = config
            seen["port"] = port
            seen["server_name"] = server_name
            seen["gateway_port"] = gateway_port
            self.startup_state = server_mod.StartupState(stage="dispatch_ready")

        def discover_builtin_skills(self, extra_skill_paths=None):
            seen["extra_skill_paths"] = extra_skill_paths
            return self

        def start(self):
            seen["started"] = True
            return FakeHandle()

    monkeypatch.setattr(server_mod, "_server_instance", None)
    monkeypatch.setattr(server_mod, "PhotoshopMcpServer", FakeServer)

    handle, state = server_mod.run_daemon(
        port=18823,
        server_name="photoshop-test",
        broker_url="http://127.0.0.1:47392",
        gateway_port=19839,
        extra_skill_paths=["/tmp/photoshop-skills"],
    )

    assert isinstance(handle, FakeHandle)
    assert state.stage == "dispatch_ready"
    assert seen["config"].broker_url == "http://127.0.0.1:47392"
    assert seen["port"] == 18823
    assert seen["server_name"] == "photoshop-test"
    assert seen["gateway_port"] == 19839
    assert seen["extra_skill_paths"] == ["/tmp/photoshop-skills"]
    assert seen["started"] is True
