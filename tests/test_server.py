"""Basic tests for PhotoshopMcpServer (without real Photoshop)."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest


def test_import():
    import dcc_mcp_photoshop

    assert dcc_mcp_photoshop.__version__
    # Verify semver format (major.minor.patch) — never pin exact version;
    # release-please bumps trigger CI failures on hardcoded assertions.
    parts = dcc_mcp_photoshop.__version__.split(".")
    assert len(parts) == 3, f"Expected semver, got {dcc_mcp_photoshop.__version__}"
    assert all(p.isdigit() for p in parts), f"Version parts must be numeric: {parts}"


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


@pytest.mark.parametrize(("requested_port", "expected_port"), [(None, None), (0, 0)])
def test_start_server_delegates_port_resolution_to_core(monkeypatch, requested_port, expected_port):
    from dcc_mcp_photoshop import server as server_module

    captured = {}

    class FakeServer:
        is_running = False

        def __init__(self, **kwargs):
            captured.update(kwargs)

        def discover_builtin_skills(self, **kwargs):
            return self

        def start(self):
            self.is_running = True
            return self

    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_PORT", "18765")
    monkeypatch.setattr(server_module, "_server_instance", None)
    monkeypatch.setattr(server_module, "PhotoshopMcpServer", FakeServer)

    server_module.start_server(port=requested_port)

    assert captured["port"] == expected_port


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


def test_check_broker_requires_connected_bridge_session(monkeypatch):
    from dcc_mcp_photoshop import server as server_module
    from dcc_mcp_photoshop.server import PhotoshopMcpServer, StartupState

    monkeypatch.setattr(server_module, "probe_broker", lambda *_args: {"ok": True, "sessions": 0})
    server = object.__new__(PhotoshopMcpServer)
    server._adapter_config = SimpleNamespace(
        broker_url="http://127.0.0.1:47391",
        broker_token="dev-token",
        broker_target="default",
        timeout=1.0,
    )
    server._startup_state = StartupState()
    server._bridge_ready = True
    server._readiness = SimpleNamespace(mark_dcc_ready=lambda value: None)
    server._push_diagnostics = lambda: None

    server._check_broker()

    assert server._startup_state.stage == "bridge_waiting"
    assert server._startup_state.failure_stage == "bridge_session"
    assert server._bridge_ready is False


def test_check_broker_marks_connected_bridge_ready(monkeypatch):
    from dcc_mcp_photoshop import server as server_module
    from dcc_mcp_photoshop.server import PhotoshopMcpServer, StartupState

    monkeypatch.setattr(server_module, "probe_broker", lambda *_args: {"ok": True, "sessions": 1})
    server = object.__new__(PhotoshopMcpServer)
    server._adapter_config = SimpleNamespace(
        broker_url="http://127.0.0.1:47391",
        timeout=1.0,
    )
    server._startup_state = StartupState()
    server._bridge_ready = False
    server._readiness = SimpleNamespace(mark_dcc_ready=lambda value: None)
    server._push_diagnostics = lambda: None

    server._check_broker()

    assert server._startup_state.stage == "broker_ready"
    assert server._bridge_ready is True


def test_readiness_waits_for_live_photoshop_bridge():
    from dcc_mcp_photoshop._readiness import ReadinessBinder

    class FakeServer:
        def set_readiness_probe(self, probe):
            self.probe = probe

    binder = ReadinessBinder()
    binder.bind(FakeServer())

    assert binder.is_ready() is False
    binder.mark_dcc_ready(True)
    assert binder.is_ready() is True


def test_bridge_watchdog_publishes_only_state_transitions():
    from dcc_mcp_photoshop._bridge_watchdog import BridgeSessionWatchdog

    payloads = iter(
        [
            {"ok": True, "sessions": 0},
            {"ok": True, "sessions": 0},
            {"ok": True, "sessions": 1},
        ]
    )
    transitions = []
    watchdog = BridgeSessionWatchdog(
        broker_url="http://127.0.0.1:47391",
        timeout=1.0,
        poll_interval=1.0,
        on_state_change=lambda ready, payload: transitions.append((ready, payload["sessions"])),
        probe=lambda *_args: next(payloads),
    )

    assert watchdog.sample() is False
    assert watchdog.sample() is False
    assert watchdog.sample() is True
    assert transitions == [(False, 0), (True, 1)]


def test_export_skill_subprocess_pythonpath_prepends_and_deduplicates(monkeypatch):
    from dcc_mcp_photoshop.server import _export_skill_subprocess_pythonpath

    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(["existing", "runtime"]))
    monkeypatch.delenv("DCC_MCP_PYTHON_EXECUTABLE", raising=False)

    _export_skill_subprocess_pythonpath(["runtime", "dependency"])

    assert os.environ["PYTHONPATH"].split(os.pathsep) == ["runtime", "dependency", "existing"]
    assert os.environ["DCC_MCP_PYTHON_EXECUTABLE"] == sys.executable


def test_skill_runtime_roots_prioritize_active_core_before_adobe(monkeypatch):
    from dcc_mcp_photoshop import server as server_module

    discovered = []

    def fake_find_spec(package_name):
        discovered.append(package_name)
        return SimpleNamespace(submodule_search_locations=[f"C:/{package_name}"], origin=None)

    monkeypatch.setattr(server_module.importlib.util, "find_spec", fake_find_spec)

    server_module._skill_runtime_roots()

    assert discovered == ["dcc_mcp_photoshop", "dcc_mcp_core", "adobe"]
