"""Regression tests for the .cube 3D LUT math and the color-lookup skill.

OFFLINE ONLY. These tests verify pure-Python LUT parsing/trilinear math and the
skill's *local* validation and descriptor construction. They do NOT talk to a
live Photoshop, MCP gateway, or adobepy broker, and are NOT native end-to-end
acceptance (real document load, pixel diff, toggle, export-copy, reopen).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from dcc_mcp_photoshop import _color_lookup as cl

_SKILLS_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills"
_ADJUSTMENT_SCRIPTS = _SKILLS_ROOT / "photoshop-adjustment" / "scripts"


def _load_skill(name: str) -> ModuleType:
    path = _ADJUSTMENT_SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Pure .cube LUT math
# ---------------------------------------------------------------------------


class TestParseCube:
    def test_parses_identity_size_2(self):
        lut = cl.parse_cube(cl.write_cube(cl.identity_lut(2)))
        assert lut.size == 2
        assert len(lut.data) == 8
        assert cl.is_identity(lut)

    def test_roundtrip_preserves_data(self):
        warm = cl.warm_lut(3)
        parsed = cl.parse_cube(cl.write_cube(warm))
        assert parsed.size == warm.size
        assert cl.max_abs_diff(list(warm.data), list(parsed.data)) < 1e-6

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "LUT_1D_SIZE 2\n0 0 0\n",
            "LUT_3D_SIZE 2\n0 0 0\n",
            "LUT_3D_SIZE 2\n" + "0 0 0\n" * 9,
            "LUT_3D_SIZE 2\n" + "0 0 nan\n" * 8,
            "LUT_3D_SIZE 2\nDOMAIN_MIN 1 1 1\nDOMAIN_MAX 0 0 0\n" + "0 0 0\n" * 8,
        ],
    )
    def test_rejects_malformed(self, text):
        with pytest.raises(ValueError):
            cl.parse_cube(text)

    def test_red_fastest_corner_ordering(self):
        lut = cl.identity_lut(2)
        # Identity LUT: sampling (1,0,0) must yield red=1 only; the third
        # lattice point (index 1) is the red-maximum corner.
        assert cl.sample(lut, 1.0, 0.0, 0.0) == pytest.approx((1.0, 0.0, 0.0))
        assert cl.sample(lut, 0.0, 1.0, 0.0) == pytest.approx((0.0, 1.0, 0.0))
        assert cl.sample(lut, 0.0, 0.0, 1.0) == pytest.approx((0.0, 0.0, 1.0))


class TestApplyLut:
    @pytest.fixture()
    def pixels(self):
        return [(1.0, 1.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.5, 0.5, 0.5)]

    def test_identity_is_a_noop(self, pixels):
        assert cl.max_abs_diff(pixels, cl.apply_lut(pixels, cl.identity_lut(2))) <= cl.IDENTITY_TOLERANCE

    def test_non_identity_changes_pixels_above_threshold(self, pixels):
        assert cl.max_abs_diff(pixels, cl.apply_lut(pixels, cl.warm_lut(2))) > cl.TRANSFORM_THRESHOLD

    def test_toggle_off_returns_source_unchanged(self, pixels):
        assert cl.max_abs_diff(pixels, cl.apply_lut(pixels, cl.warm_lut(2), enabled=False)) == 0.0

    def test_source_pixels_are_never_mutated(self, pixels):
        before = list(pixels)
        cl.apply_lut(pixels, cl.warm_lut(2))
        assert before == pixels

    def test_export_copy_and_reopen_match(self, pixels):
        warm = cl.warm_lut(2)
        applied = cl.apply_lut(pixels, warm)
        reopened = cl.apply_lut(pixels, cl.parse_cube(cl.write_cube(warm)))
        assert cl.max_abs_diff(applied, reopened) <= cl.IDENTITY_TOLERANCE
        assert cl.max_abs_diff(pixels, applied) > cl.TRANSFORM_THRESHOLD

    def test_max_abs_diff_rejects_length_mismatch(self):
        with pytest.raises(ValueError):
            cl.max_abs_diff([(1.0, 1.0, 1.0)], [])


# ---------------------------------------------------------------------------
# apply_color_lookup skill — local validation + descriptor construction
# ---------------------------------------------------------------------------


class TestApplyColorLookupSkill:
    @pytest.fixture()
    def cube_file(self, tmp_path):
        path = tmp_path / "warm.cube"
        path.write_text(cl.write_cube(cl.warm_lut(2)), encoding="utf-8")
        return path

    def test_descriptor_is_color_lookup_adjustment_layer(self, cube_file):
        mod = _load_skill("apply_color_lookup.py")
        descriptor = mod._build_descriptor(str(cube_file), enabled=True, opacity=100.0, layer_name="My LUT")
        assert descriptor["_obj"] == "make"
        assert descriptor["_target"] == [{"_ref": "adjustmentLayer"}]
        using = descriptor["using"]
        assert using["type"]["_obj"] == "colorLookup"
        assert using["type"]["dataSource"]["_value"] == "LUT3DFile"
        assert using["type"]["LUT3DFile"]["_path"] == str(cube_file)
        assert using["enabled"] is True
        assert using["name"] == "My LUT"

    def test_success_path_returns_result_context(self, cube_file, monkeypatch):
        mod = _load_skill("apply_color_lookup.py")
        app = Mock()
        app.batch_play.return_value = [{"layerID": 7}]
        monkeypatch.setattr(mod, "Photoshop", lambda: app)

        result = mod.apply_color_lookup(lut_path=str(cube_file))

        assert result["success"] is True
        assert result["context"]["lut_filename"] == "warm.cube"
        assert result["context"]["lut_size"] == 2
        assert result["context"]["is_identity"] is False
        app.batch_play.assert_called_once()
        sent = app.batch_play.call_args.args[0][0]
        assert sent["using"]["type"]["_obj"] == "colorLookup"

    def test_toggle_and_opacity_flow_into_descriptor(self, cube_file, monkeypatch):
        mod = _load_skill("apply_color_lookup.py")
        app = Mock()
        app.batch_play.return_value = []
        monkeypatch.setattr(mod, "Photoshop", lambda: app)

        mod.apply_color_lookup(lut_path=str(cube_file), enabled=False, opacity=42.0)

        sent = app.batch_play.call_args.args[0][0]
        assert sent["using"]["enabled"] is False
        assert sent["using"]["opacity"] == 42.0

    def test_identity_lut_is_reported(self, tmp_path, monkeypatch):
        cube = tmp_path / "identity.cube"
        cube.write_text(cl.write_cube(cl.identity_lut(2)), encoding="utf-8")
        mod = _load_skill("apply_color_lookup.py")
        app = Mock()
        app.batch_play.return_value = []
        monkeypatch.setattr(mod, "Photoshop", lambda: app)

        result = mod.apply_color_lookup(lut_path=str(cube))

        assert result["success"] is True
        assert result["context"]["is_identity"] is True

    @pytest.mark.parametrize(
        "suffix,content,kwargs",
        [
            ("missing.cube", None, {}),  # file not created
            ("wrong.txt", "LUT_3D_SIZE 2\n" + "0 0 0\n" * 8, {}),
            ("bad.cube", "LUT_1D_SIZE 2\n0 0 0\n", {}),
            ("opacity.cube", "LUT_3D_SIZE 2\n" + "0 0 0\n" * 8, {"opacity": 500.0}),
        ],
    )
    def test_invalid_inputs_fail_before_host_call(self, tmp_path, monkeypatch, suffix, content, kwargs):
        mod = _load_skill("apply_color_lookup.py")
        app = Mock()
        monkeypatch.setattr(mod, "Photoshop", lambda: app)
        path = tmp_path / suffix
        if content is not None:
            path.write_text(content, encoding="utf-8")

        result = mod.apply_color_lookup(lut_path=str(path), **kwargs)

        assert result["success"] is False
        app.batch_play.assert_not_called()
