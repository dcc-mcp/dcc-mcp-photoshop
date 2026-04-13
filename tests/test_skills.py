"""Tests for skill scripts — get_document_info.py and list_layers.py.

Skill scripts live under ``skills/photoshop-document/scripts/`` which uses a
hyphenated directory name and cannot be imported as a Python module directly.
We load the scripts via ``importlib.util.spec_from_file_location``.

The ``inject_bridge`` fixture wires a connected ``PhotoshopBridge`` (backed
by the mock UXP server from conftest.py) into ``dcc_mcp_photoshop.api._bridge``
so ``get_bridge()`` works without a real Photoshop installation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

# Path to skill scripts
_SKILLS_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills"
_DOCUMENT_SCRIPTS = _SKILLS_ROOT / "photoshop-document" / "scripts"


def _load_script(name: str) -> ModuleType:
    """Load a skill script by filename from the photoshop-document skills dir."""
    path = _DOCUMENT_SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def inject_bridge(connected_bridge):
    """Inject the connected mock bridge into the api module singleton."""
    import dcc_mcp_photoshop.api as api_mod

    api_mod._bridge = connected_bridge
    yield
    api_mod._bridge = None


# ---------------------------------------------------------------------------
# get_document_info skill
# ---------------------------------------------------------------------------


class TestGetDocumentInfoSkill:
    def test_success_result_shape(self):
        mod = _load_script("get_document_info.py")
        result = mod.get_document_info()
        assert result["success"] is True
        assert "Untitled-1.psd" in result["message"]

    def test_returns_document_name(self):
        mod = _load_script("get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["document_name"] == "Untitled-1.psd"

    def test_returns_dimensions(self):
        mod = _load_script("get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["width"] == 1920
        assert result["context"]["height"] == 1080

    def test_returns_resolution(self):
        mod = _load_script("get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["resolution"] == 72.0

    def test_main_entrypoint(self):
        mod = _load_script("get_document_info.py")
        result = mod.main()
        assert result["success"] is True

    def test_no_bridge_returns_error_result(self):
        """When bridge is not connected, skill_entry returns a failure dict."""
        import dcc_mcp_photoshop.api as api_mod

        api_mod._bridge = None  # disconnect bridge for this test
        mod = _load_script("get_document_info.py")

        # @skill_entry catches exceptions and returns a failure dict
        result = mod.get_document_info()
        assert result["success"] is False
        assert "PhotoshopNotAvailableError" in result.get("error", "") or \
               "bridge" in result.get("message", "").lower()


# ---------------------------------------------------------------------------
# list_layers skill
# ---------------------------------------------------------------------------


class TestListLayersSkill:
    def test_success_result_shape(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers()
        assert result["success"] is True

    def test_returns_layer_count(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers()
        assert result["context"]["count"] == 3

    def test_returns_layer_names(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers()
        names = result["context"]["layers"]
        assert "Background" in names
        assert "Layer 1" in names
        assert "Hidden Layer" in names

    def test_exclude_hidden_layers(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers(include_hidden=False)
        assert result["success"] is True
        assert result["context"]["count"] == 2
        assert "Hidden Layer" not in result["context"]["layers"]

    def test_include_hidden_param_reflected(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers(include_hidden=True)
        assert result["context"]["include_hidden"] is True

    def test_message_contains_count(self):
        mod = _load_script("list_layers.py")
        result = mod.list_layers()
        assert "3" in result["message"]

    def test_main_entrypoint(self):
        mod = _load_script("list_layers.py")
        result = mod.main()
        assert result["success"] is True
