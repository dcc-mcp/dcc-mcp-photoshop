"""Tests for dcc_mcp_photoshop.api — skill authoring helpers.

Tests cover:
- ps_success / ps_error / ps_warning / ps_from_exception result shapes
- get_bridge() raises PhotoshopNotAvailableError when disconnected
- get_bridge() returns bridge when connected (via module-level singleton)
- is_photoshop_available() reflects bridge state
- with_photoshop decorator catches PhotoshopNotAvailableError and Exception
- photoshop_capabilities() returns correct DccCapabilities
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


class TestResultHelpers:
    def test_ps_success_basic(self):
        from dcc_mcp_photoshop.api import ps_success

        r = ps_success("done")
        assert r["success"] is True
        assert r["message"] == "done"

    def test_ps_success_with_context(self):
        from dcc_mcp_photoshop.api import ps_success

        r = ps_success("got info", name="Untitled-1", width=1920)
        assert r["success"] is True
        assert r["context"]["name"] == "Untitled-1"
        assert r["context"]["width"] == 1920

    def test_ps_success_with_prompt(self):
        from dcc_mcp_photoshop.api import ps_success

        r = ps_success("done", prompt="Next: list layers")
        assert r["prompt"] == "Next: list layers"

    def test_ps_error_basic(self):
        from dcc_mcp_photoshop.api import ps_error

        r = ps_error("failed", "ConnectionRefused")
        assert r["success"] is False
        assert r["message"] == "failed"
        assert r["error"] == "ConnectionRefused"

    def test_ps_error_with_solutions(self):
        from dcc_mcp_photoshop.api import ps_error

        r = ps_error("no doc", "NoActiveDocument", possible_solutions=["Open a file"])
        assert r["success"] is False

    def test_ps_warning_is_success(self):
        from dcc_mcp_photoshop.api import ps_warning

        r = ps_warning("saved with warning", warning="minor issue")
        assert r["success"] is True
        assert "warning" in r["context"] or r["message"] == "saved with warning"

    def test_ps_from_exception(self):
        from dcc_mcp_photoshop.api import ps_from_exception

        try:
            raise ValueError("something went wrong")
        except Exception as exc:
            r = ps_from_exception(exc, "operation failed")

        assert r["success"] is False
        assert "something went wrong" in r["error"] or "ValueError" in r["error"]


# ---------------------------------------------------------------------------
# Bridge singleton helpers
# ---------------------------------------------------------------------------


class TestBridgeSingleton:
    def setup_method(self):
        """Reset the module-level bridge singleton before each test."""
        import dcc_mcp_photoshop.api as api_mod
        api_mod._bridge = None

    def test_is_photoshop_available_false_when_none(self):
        from dcc_mcp_photoshop.api import is_photoshop_available

        assert is_photoshop_available() is False

    def test_get_bridge_raises_when_none(self):
        from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, get_bridge

        with pytest.raises(PhotoshopNotAvailableError):
            get_bridge()

    def test_get_bridge_raises_when_disconnected(self, mock_uxp_server):
        """get_bridge() raises if the bridge exists but is not connected."""
        import dcc_mcp_photoshop.api as api_mod
        from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, get_bridge
        from dcc_mcp_photoshop.bridge import PhotoshopBridge

        host, port = mock_uxp_server
        bridge = PhotoshopBridge(host=host, port=port)
        # Not connected yet
        api_mod._bridge = bridge

        with pytest.raises(PhotoshopNotAvailableError):
            get_bridge()

    def test_get_bridge_returns_bridge_when_connected(self, connected_bridge, mock_uxp_server):
        """get_bridge() returns the bridge when it is connected."""
        import dcc_mcp_photoshop.api as api_mod
        from dcc_mcp_photoshop.api import get_bridge, is_photoshop_available

        api_mod._bridge = connected_bridge

        assert is_photoshop_available() is True
        b = get_bridge()
        assert b is connected_bridge

    def test_is_photoshop_available_true_when_connected(self, connected_bridge):
        import dcc_mcp_photoshop.api as api_mod
        from dcc_mcp_photoshop.api import is_photoshop_available

        api_mod._bridge = connected_bridge
        assert is_photoshop_available() is True


# ---------------------------------------------------------------------------
# with_photoshop decorator
# ---------------------------------------------------------------------------


class TestWithPhotoshopDecorator:
    def setup_method(self):
        import dcc_mcp_photoshop.api as api_mod
        api_mod._bridge = None

    def test_catches_not_available_error(self):
        from dcc_mcp_photoshop.api import PhotoshopNotAvailableError, with_photoshop

        @with_photoshop
        def my_skill(**kwargs):
            raise PhotoshopNotAvailableError("bridge not connected")

        result = my_skill()
        assert result["success"] is False
        assert "Photoshop not available" in result["message"]

    def test_catches_general_exception(self):
        from dcc_mcp_photoshop.api import with_photoshop

        @with_photoshop
        def buggy_skill(**kwargs):
            raise RuntimeError("unexpected bug")

        result = buggy_skill()
        assert result["success"] is False

    def test_passes_through_success(self):
        from dcc_mcp_photoshop.api import ps_success, with_photoshop

        @with_photoshop
        def good_skill(**kwargs):
            return ps_success("all good", count=5)

        result = good_skill()
        assert result["success"] is True
        assert result["context"]["count"] == 5

    def test_passes_kwargs(self):
        from dcc_mcp_photoshop.api import ps_success, with_photoshop

        @with_photoshop
        def echo_skill(name: str = "default", **kwargs):
            return ps_success("echo", name=name)

        result = echo_skill(name="test")
        assert result["context"]["name"] == "test"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_photoshop_capabilities_no_embedded_python(self):
        from dcc_mcp_photoshop.api import photoshop_capabilities

        caps = photoshop_capabilities()
        assert caps.has_embedded_python is False

    def test_photoshop_capabilities_bridge_kind(self):
        from dcc_mcp_photoshop.api import photoshop_capabilities

        caps = photoshop_capabilities()
        assert caps.bridge_kind == "websocket"

    def test_photoshop_capabilities_bridge_endpoint(self):
        from dcc_mcp_photoshop.api import photoshop_capabilities

        caps = photoshop_capabilities()
        assert "9001" in caps.bridge_endpoint

    def test_photoshop_capabilities_feature_flags(self):
        from dcc_mcp_photoshop.api import photoshop_capabilities

        caps = photoshop_capabilities()
        assert caps.scene_manager is True
        assert caps.selection is True
        assert caps.file_operations is True
        assert caps.snapshot is True

    def test_capabilities_dict_matches(self):
        from dcc_mcp_photoshop.capabilities import PHOTOSHOP_CAPABILITIES_DICT, photoshop_capabilities

        caps = photoshop_capabilities()
        assert caps.has_embedded_python == PHOTOSHOP_CAPABILITIES_DICT["has_embedded_python"]
        assert caps.bridge_kind == PHOTOSHOP_CAPABILITIES_DICT["bridge_kind"]
