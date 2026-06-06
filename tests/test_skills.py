"""Tests for skill scripts migrated to adobepy facade.

All tests use ``fake_broker_client`` which replaces BrokerClient with a
FakeClient that returns realistic mock data.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SKILLS_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills"
_DOCUMENT_SCRIPTS = _SKILLS_ROOT / "photoshop-document" / "scripts"
_LAYERS_SCRIPTS = _SKILLS_ROOT / "photoshop-layers" / "scripts"
_IMAGE_SCRIPTS = _SKILLS_ROOT / "photoshop-image" / "scripts"
_TEXT_SCRIPTS = _SKILLS_ROOT / "photoshop-text" / "scripts"


def _load_script(scripts_dir: Path, name: str) -> ModuleType:
    path = scripts_dir / name
    spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.usefixtures("fake_broker_client")


# ---------------------------------------------------------------------------
# get_document_info skill
# ---------------------------------------------------------------------------


class TestGetDocumentInfoSkill:
    def test_success_result_shape(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "get_document_info.py")
        result = mod.get_document_info()
        assert result["success"] is True

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
        assert result["context"]["count"] == 4

    def test_returns_layer_names(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers()
        names = result["context"]["layers"]
        assert "Background" in names
        assert "Layer 1" in names
        assert "Hidden Layer" in names
        assert "MyText" in names

    def test_exclude_hidden_layers(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers(include_hidden=False)
        assert result["success"] is True
        assert result["context"]["count"] == 3
        assert "Hidden Layer" not in result["context"]["layers"]

    def test_include_hidden_param_reflected(self):
        mod = _load_script(_DOCUMENT_SCRIPTS, "list_layers.py")
        result = mod.list_layers(include_hidden=True)
        assert result["context"]["include_hidden"] is True

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
        assert "Layer 1 copy" in str(result["context"]["layer_name"])

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
        assert result["context"]["document_name"] is not None
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

    def test_create_text_layer_custom_name(self):
        """The custom layer name must appear in the result, not 'New Layer'."""
        mod = _load_script(_TEXT_SCRIPTS, "create_text_layer.py")
        result = mod.create_text_layer(content="Hello", name="MyText")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "MyText"

    def test_create_text_layer_defaults(self):
        mod = _load_script(_TEXT_SCRIPTS, "create_text_layer.py")
        result = mod.create_text_layer(content="Test")
        assert result["success"] is True

    def test_update_text_layer(self):
        mod = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        result = mod.update_text_layer(name="MyText", content="Updated text")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "MyText"

    def test_update_text_layer_alignment(self):
        """Alignment must be set via paragraph style, not character style."""
        from tests.conftest import FakeClient

        mod = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        result = mod.update_text_layer(name="MyText", alignment="center")
        assert result["success"] is True
        # Verify paragraph style was the channel used
        assert FakeClient._last_set_paragraph_style is not None
        assert FakeClient._last_set_paragraph_style.get("alignment") == "center"

    def test_update_text_layer_alignment_roundtrip(self):
        """After setting alignment, subsequent read must reflect the change."""
        mod_update = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        mod_get = _load_script(_TEXT_SCRIPTS, "get_text_layer_info.py")

        # Update alignment
        result = mod_update.update_text_layer(name="MyText", alignment="center")
        assert result["success"] is True

        # Read back — alignment should be the updated value
        result = mod_get.get_text_layer_info(name="MyText")
        assert result["success"] is True
        assert result["context"]["alignment"] == "center"

    def test_update_text_layer_not_found(self):
        """Updating a non-existent layer must fail, not silently fall back."""
        mod = _load_script(_TEXT_SCRIPTS, "update_text_layer.py")
        result = mod.update_text_layer(name="DoesNotExist", content="New")
        assert result["success"] is False
        assert "not found" in result.get("message", "") or "not found" in result.get("error", "")

    def test_get_text_layer_info(self):
        mod = _load_script(_TEXT_SCRIPTS, "get_text_layer_info.py")
        result = mod.get_text_layer_info(name="MyText")
        assert result["success"] is True
        assert result["context"]["layer_name"] == "MyText"
        assert result["context"]["content"] == "Hello, World!"

    def test_get_text_layer_info_style_fields(self):
        """Text style fields (font, size, color, bold, italic) must be populated."""
        mod = _load_script(_TEXT_SCRIPTS, "get_text_layer_info.py")
        result = mod.get_text_layer_info(name="MyText")
        assert result["success"] is True
        ctx = result["context"]
        assert ctx["font"] == "ArialMT"
        assert ctx["size"] == 48
        assert ctx["color"] == "#000000"
        assert ctx["bold"] is False
        assert ctx["italic"] is False
        assert ctx["alignment"] == "left"

    def test_get_text_layer_info_not_found(self):
        """Querying a non-existent layer must fail, not silently return activeText."""
        mod = _load_script(_TEXT_SCRIPTS, "get_text_layer_info.py")
        result = mod.get_text_layer_info(name="DoesNotExist")
        assert result["success"] is False
        assert "not found" in result.get("message", "") or "not found" in result.get("error", "")
