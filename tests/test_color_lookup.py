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


# ---------------------------------------------------------------------------
# CodeRabbit PR #154 findings — offline regressions for the narrow parse/identity
# fixes. Each case has a negative (malformed LUT rejected) and a normal (valid
# LUT still accepted) counterpart.
# ---------------------------------------------------------------------------


class TestParseCubeHardening:
    def test_excess_data_lines_fail_fast(self, monkeypatch):
        # Finding 4434889399: a .cube declaring size 2 must not buffer an
        # unbounded number of data lines before the final count check.
        calls = {"n": 0}
        original = cl._parse_triple

        def counting(parts, label):
            calls["n"] += 1
            return original(parts, label)

        monkeypatch.setattr(cl, "_parse_triple", counting)
        text = "LUT_3D_SIZE 2\n" + "0 0 0\n" * 20000
        with pytest.raises(ValueError, match="more than 8 data lines"):
            cl.parse_cube(text)
        # Only the declared capacity (8) plus the first overflow line is parsed.
        assert calls["n"] <= 9

    def test_exact_capacity_lut_still_parses(self):
        # Normal counterpart: a fully-populated LUT is unaffected by the guard.
        text = "LUT_3D_SIZE 2\n" + "0 0 0\n" * 8
        lut = cl.parse_cube(text)
        assert lut.size == 2
        assert len(lut.data) == 8

    @pytest.mark.parametrize("declaration", ["LUT_3D_SIZE 1", "LUT_3D_SIZE 257"])
    def test_size_out_of_range_rejected(self, declaration):
        with pytest.raises(ValueError, match="out of range"):
            cl.parse_cube(declaration + "\n" + "0 0 0\n" * 8)

    @pytest.mark.parametrize(
        "directive",
        [
            "DOMAIN_MIN nan 0 0",
            "DOMAIN_MIN 0 nan 0",
            "DOMAIN_MAX 1 inf 1",
            "DOMAIN_MAX 1 1 -inf",
        ],
    )
    def test_non_finite_domain_rejected(self, directive):
        # Finding 4434889403: a nan/inf domain bound must not pass parse_cube.
        text = f"LUT_3D_SIZE 2\n{directive}\n" + "0 0 0\n" * 8
        with pytest.raises(ValueError, match="non-finite"):
            cl.parse_cube(text)

    @pytest.mark.parametrize(
        "directive",
        [
            "DOMAIN_MIN 0 0 0 EXTRA",
            "DOMAIN_MIN 0 0 0 0 0",
            "DOMAIN_MAX 1 1 1 EXTRA",
        ],
    )
    def test_domain_extra_field_rejected(self, directive):
        # Finding 4434889405: extra fields on a domain directive are rejected,
        # not silently truncated.
        text = f"LUT_3D_SIZE 2\n{directive}\n" + "0 0 0\n" * 8
        with pytest.raises(ValueError):
            cl.parse_cube(text)

    def test_finite_custom_domain_still_parses(self):
        # Normal counterpart: a valid finite custom domain is accepted.
        text = "LUT_3D_SIZE 2\nDOMAIN_MIN 0.1 0.2 0.3\nDOMAIN_MAX 0.9 0.8 0.7\n" + "0 0 0\n" * 8
        lut = cl.parse_cube(text)
        assert lut.domain_min == (0.1, 0.2, 0.3)
        assert lut.domain_max == (0.9, 0.8, 0.7)

    def test_is_identity_rejects_non_default_domain_mismatch(self):
        # Finding 4434889409: default identity data with a non-unit domain is
        # NOT an identity transform; is_identity must account for the domain.
        lut = cl.CubeLut(
            size=2,
            data=cl.identity_lut(2).data,
            domain_min=(0.25, 0.25, 0.25),
            domain_max=(0.75, 0.75, 0.75),
        )
        assert cl.sample(lut, 0.25, 0.25, 0.25) == (0.0, 0.0, 0.0)
        assert cl.is_identity(lut) is False

    def test_is_identity_accepts_domain_consistent_identity(self):
        # Normal counterpart: data equal to the domain coordinate at each
        # lattice point is an identity transform even on a non-unit domain.
        span = 1  # size 2
        lo, hi = 0.25, 0.75
        data = tuple(
            (
                lo + (r / span) * (hi - lo),
                lo + (g / span) * (hi - lo),
                lo + (b / span) * (hi - lo),
            )
            for b in range(2)
            for g in range(2)
            for r in range(2)
        )
        lut = cl.CubeLut(
            size=2,
            data=data,
            domain_min=(lo, lo, lo),
            domain_max=(hi, hi, hi),
        )
        assert cl.is_identity(lut) is True

    def test_is_identity_default_identity_unchanged(self):
        assert cl.is_identity(cl.identity_lut(2)) is True
        assert cl.is_identity(cl.parse_cube(cl.write_cube(cl.identity_lut(3)))) is True


class TestWriteCubePrecision:
    """Round-2 finding 4435462698: tiny domains/data must survive serialization."""

    def test_tiny_domain_round_trips_without_collapse(self):
        # Boundary regression: a valid, non-zero-width domain far below 5e-10
        # must not be rounded to 0.000000000 by write_cube. The old ':.9f'
        # format turned DOMAIN_MAX into zero width, so parse_cube(write_cube())
        # raised "invalid LUT domain".
        tiny = 1e-10
        text = f'TITLE "tiny"\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX {tiny} {tiny} {tiny}\nLUT_3D_SIZE 2\n' + "0 0 0\n" * 8
        lut = cl.parse_cube(text)
        assert lut.domain_max == (tiny, tiny, tiny)

        written = cl.write_cube(lut)
        dmax_line = [ln for ln in written.splitlines() if ln.startswith("DOMAIN_MAX")][0]
        assert "0.000000000 " not in dmax_line  # not collapsed to zero
        assert "1e-10" in dmax_line  # preserved via scientific notation

        reparsed = cl.parse_cube(written)  # must NOT raise ValueError
        assert reparsed.domain_min == (0.0, 0.0, 0.0)
        assert reparsed.domain_max == (tiny, tiny, tiny)

    def test_tiny_data_values_round_trip_exactly(self):
        # Normal regression for the data path: small non-zero lattice values
        # are preserved with the same round-trip-safe representation used for
        # the domain bounds (the finding asks to apply it to LUT data too).
        tiny = 1e-10
        data = tuple((tiny, 2 * tiny, 3 * tiny) for _ in range(8))
        lut = cl.CubeLut(size=2, data=data)
        parsed = cl.parse_cube(cl.write_cube(lut))
        assert cl.max_abs_diff(list(data), list(parsed.data)) == 0.0

    def test_normal_unit_domain_stays_clean_decimal(self):
        # Normal regression: ordinary unit-domain values remain readable
        # decimals; only extreme magnitudes use scientific notation.
        written = cl.write_cube(cl.identity_lut(2))
        dmax_line = [ln for ln in written.splitlines() if ln.startswith("DOMAIN_MAX")][0]
        assert dmax_line == "DOMAIN_MAX 1.0 1.0 1.0"
        assert cl.is_identity(cl.parse_cube(written)) is True
