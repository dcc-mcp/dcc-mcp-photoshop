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
_LAYERS_SCRIPTS   = _SKILLS_ROOT / "photoshop-layers" / "scripts"
_IMAGE_SCRIPTS    = _SKILLS_ROOT / "photoshop-image" / "scripts"
_TEXT_SCRIPTS     = _SKILLS_ROOT / "photoshop-text" / "scripts"


def _load_script(scripts_dir: Path, name: str) -> ModuleType:
    """Load a skill script by filename."""
    path = scripts_dir / name
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
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.get_document_info()
        assert result["success"] is True
        assert "Untitled-1.psd" in result["message"]

    def test_returns_document_name(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["document_name"] == "Untitled-1.psd"

    def test_returns_dimensions(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["width"] == 1920
        assert result["context"]["height"] == 1080

    def test_returns_resolution(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.get_document_info()
        assert result["context"]["resolution"] == 72.0

    def test_main_entrypoint(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.main()
        assert result["success"] is True

    def test_no_bridge_returns_error_result(self):
        """When bridge is not connected, skill_entry returns a failure dict."""
        import dcc_mcp_photoshop.api as api_mod

        api_mod._bridge = None  # disconnect bridge for this test
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")

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
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers()
        assert result["success"] is True

    def test_returns_layer_count(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers()
        assert result["context"]["count"] == 3

    def test_returns_layer_names(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers()
        names = result["context"]["layers"]
        assert "Background" in names
        assert "Layer 1" in names
        assert "Hidden Layer" in names

    def test_exclude_hidden_layers(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers(include_hidden=False)
        assert result["success"] is True
        assert result["context"]["count"] == 2
        assert "Hidden Layer" not in result["context"]["layers"]

    def test_include_hidden_param_reflected(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers(include_hidden=True)
        assert result["context"]["include_hidden"] is True

    def test_message_contains_count(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers()
        assert "3" in result["message"]

    def test_main_entrypoint(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.main()
        assert result["success"] is True


# ---------------------------------------------------------------------------
# photoshop-layers skills
# ---------------------------------------------------------------------------


class TestLayerSkills:
    def test_create_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "create_layer.py")
        result = mod.create_layer(name="TestLayer")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "TestLayer"

    def test_create_group_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "create_layer.py")
        result = mod.create_layer(name="MyGroup", layer_type="group")
        assert result["success"] is True

    def test_delete_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "delete_layer.py")
        result = mod.delete_layer(name="Background")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "Background"

    def test_duplicate_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "duplicate_layer.py")
        result = mod.duplicate_layer(name="Layer 1", new_name="Layer 1 copy")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "Layer 1 copy"

    def test_rename_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "rename_layer.py")
        result = mod.rename_layer(name="Layer 1", new_name="Renamed")
        assert result["success"] is True
        assert result["context"]["new_name"] == "Renamed"

    def test_set_layer_opacity(self):
        mod = _load_script(_LAYERS_SCRIPTS, "set_layer_opacity.py")
        result = mod.set_layer_opacity(name="Layer 1", opacity=50)
        assert result["success"] is True
        assert result["context"]["opacity"] == 50

    def test_set_layer_visibility_hide(self):
        mod = _load_script(_LAYERS_SCRIPTS, "set_layer_visibility.py")
        result = mod.set_layer_visibility(name="Layer 1", visible=False)
        assert result["success"] is True
        assert result["context"]["visible"] is False

    def test_set_layer_visibility_show(self):
        mod = _load_script(_LAYERS_SCRIPTS, "set_layer_visibility.py")
        result = mod.set_layer_visibility(name="Hidden Layer", visible=True)
        assert result["success"] is True
        assert result["context"]["visible"] is True

    def test_set_layer_blend_mode(self):
        mod = _load_script(_LAYERS_SCRIPTS, "set_layer_blend_mode.py")
        result = mod.set_layer_blend_mode(name="Layer 1", blend_mode="multiply")
        assert result["success"] is True
        assert result["context"]["blend_mode"] == "multiply"

    def test_fill_layer(self):
        mod = _load_script(_LAYERS_SCRIPTS, "fill_layer.py")
        result = mod.fill_layer(name="Layer 1", color="#ff0000")
        assert result["success"] is True
        assert result["context"]["color"] == "#ff0000"


# ---------------------------------------------------------------------------
# photoshop-image skills
# ---------------------------------------------------------------------------


class TestImageSkills:
    def test_create_document(self):
        mod = _load_script(_IMAGE_SCRIPTS, "create_document.py")
        result = mod.create_document(name="New Doc", width=800, height=600)
        assert result["success"] is True
        assert result["context"]["document_name"] == "New Doc"
        assert result["context"]["width"] == 800
        assert result["context"]["height"] == 600

    def test_create_document_defaults(self):
        mod = _load_script(_IMAGE_SCRIPTS, "create_document.py")
        result = mod.create_document()
        assert result["success"] is True
        assert result["context"]["width"] == 1920
        assert result["context"]["height"] == 1080

    def test_export_document(self):
        mod = _load_script(_IMAGE_SCRIPTS, "export_document.py")
        result = mod.export_document(path="test.png", format="png")
        assert result["success"] is True
        assert result["context"]["format"] == "png"

    def test_export_document_jpg(self):
        mod = _load_script(_IMAGE_SCRIPTS, "export_document.py")
        result = mod.export_document(path="test.jpg", format="jpg", quality=85)
        assert result["success"] is True

    def test_save_document(self):
        mod = _load_script(_IMAGE_SCRIPTS, "save_document.py")
        result = mod.save_document()
        assert result["success"] is True
        assert result["context"]["saved"] is True

    def test_resize_canvas(self):
        mod = _load_script(_IMAGE_SCRIPTS, "resize_canvas.py")
        result = mod.resize_canvas(width=2560, height=1440)
        assert result["success"] is True
        assert result["context"]["width"] == 2560
        assert result["context"]["height"] == 1440

    def test_resize_image(self):
        mod = _load_script(_IMAGE_SCRIPTS, "resize_image.py")
        result = mod.resize_image(width=1280, height=720)
        assert result["success"] is True
        assert result["context"]["width"] == 1280

    def test_flatten_image(self):
        mod = _load_script(_IMAGE_SCRIPTS, "flatten_image.py")
        result = mod.flatten_image()
        assert result["success"] is True
        assert result["context"]["flattened"] is True

    def test_merge_visible_layers(self):
        mod = _load_script(_IMAGE_SCRIPTS, "merge_visible_layers.py")
        result = mod.merge_visible_layers()
        assert result["success"] is True
        assert result["context"]["merged"] is True


# ---------------------------------------------------------------------------
# photoshop-text skills
# ---------------------------------------------------------------------------


class TestTextSkills:
    def test_create_text_layer(self):
        mod = _load_script(_TEXT_SCRIPTS, "create_text_layer.py")
        result = mod.create_text_layer(
            content="Hello, World!",
            font="ArialMT",
            size=72,
            color="#ffffff",
        )
        assert result["success"] is True
        assert result["context"]["content"] == "Hello, World!"
        assert result["context"]["font"] == "ArialMT"
        assert result["context"]["size"] == 72

    def test_create_text_layer_defaults(self):
        mod = _load_script(_TEXT_SCRIPTS, "create_text_layer.py")
        result = mod.create_text_layer(content="Test")
        assert result["success"] is True

    def test_update_text_layer(self):
        mod = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        result = mod.update_text_layer(name="MyText", content="Updated text")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "MyText"

    def test_update_text_layer_partial(self):
        """Only provided fields should appear in updated_fields."""
        mod = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        result = mod.update_text_layer(name="MyText", size=96.0)
        assert result["success"] is True
        assert "size" in result["context"]["updated_fields"]
        assert "content" not in result["context"]["updated_fields"]

    def test_get_text_layer_info(self):
        mod = _load_script(_TEXT_SCRIPTS, "get_text_layer_info.py")
        result = mod.get_text_layer_info(name="MyText")
        assert result["success"] is True
        assert result["context"]["content"] == "Hello, World!"
        assert result["context"]["font"] == "ArialMT"
        assert result["context"]["color"] == "#000000"

