"""Skill-level tests for silent no-op feedback on batch layer operations.

These cover the tool surface described in the gap report: a batch of layer
writes must be able to tell the caller which layers contribute nothing to the
composite, instead of reporting success for every one of them.

The pixel read-back is replaced by a scripted sampler, so the tests still run
the real :func:`probe_layer_effect` decision logic without Photoshop.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from dcc_mcp_photoshop import _layer_effect

_SKILLS_ROOT = Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills"
_LAYERS_SCRIPTS = _SKILLS_ROOT / "photoshop-layers" / "scripts"

WHITE = [255.0, 255.0, 255.0]
BLUE = [28.0, 38.0, 66.0]

_BOUNDS = [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}]


def _load_script(name: str) -> ModuleType:
    path = _LAYERS_SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _layer(name="Layer 1", visible=True):
    layer = Mock()
    layer.name = name
    layer.visible = visible
    return layer


def _app(layers, bounds=None):
    """Return a Photoshop stand-in whose ``batch_play`` answers bounds queries."""
    app = Mock()
    document = Mock()
    document.layers = layers
    document.width = 1200
    document.height = 800
    app.activeDocument = document
    app.batch_play.side_effect = [bounds if bounds is not None else _BOUNDS, None, None]
    return app


def _scripted_probe(colours, bounds=None):
    """Build a ``probe_layer_effect`` replacement driven by ``colours``.

    ``colours`` maps a layer name to the RGB triple read while the layer is
    *visible*. Hiding a layer always reveals the white backdrop, which is the
    situation from the reported reproduction.
    """

    def probe(app, name, **kwargs):
        kwargs.pop("sampler", None)
        app.batch_play.side_effect = [bounds if bounds is not None else _BOUNDS, None, None]
        reads = {"count": 0}

        def read(_app, points):
            reads["count"] += 1
            if reads["count"] == 1:
                colour = colours.get(name, WHITE)
                return [list(colour) for _ in points]
            return [list(WHITE) for _ in points]

        return _layer_effect.probe_layer_effect(app, name, sampler=read, **kwargs)

    return probe


def _verification_must_not_run(_app, name, **_kwargs):
    raise AssertionError("verification must not run when verify=False")


class TestVerifyLayerBatch:
    def test_flags_the_layer_that_vanishes_into_the_backdrop(self):
        # batch_04 is OVERLAY-on-white: identical with and without the layer.
        module = _load_script("verify_layer_batch.py")
        app = _app([_layer("batch_01"), _layer("batch_04")])
        module.Photoshop = lambda: app
        module.probe_layer_effect = _scripted_probe({"batch_01": BLUE, "batch_04": WHITE})

        result = module.verify_layer_batch()

        assert result["success"] is True
        assert result["context"]["layer_count"] == 2
        assert result["context"]["no_op_layers"] == ["batch_04"]
        assert result["context"]["no_op_count"] == 1
        assert "batch_04" in result["context"]["warning"]
        assert "batch_01" not in result["context"]["warning"]

    def test_reports_nothing_when_every_layer_is_visible(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: _app([_layer("batch_01")])
        module.probe_layer_effect = _scripted_probe({"batch_01": BLUE})

        result = module.verify_layer_batch()

        assert result["context"]["no_op_layers"] == []
        assert result["context"]["no_op_count"] == 0
        assert result["context"]["warning"] is None

    def test_defaults_to_every_top_level_layer(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: _app([_layer("batch_01"), _layer("batch_02")])
        module.probe_layer_effect = _scripted_probe({"batch_01": BLUE, "batch_02": BLUE})

        result = module.verify_layer_batch()

        assert result["context"]["checked_layers"] == ["batch_01", "batch_02"]

    def test_explicit_layer_list_is_honoured(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: _app([_layer("batch_01"), _layer("batch_02")])
        module.probe_layer_effect = _scripted_probe({"batch_02": WHITE})

        result = module.verify_layer_batch(layers=["batch_02"])

        assert result["context"]["checked_layers"] == ["batch_02"]
        assert result["context"]["layer_count"] == 1

    def test_warning_separates_measured_no_ops_from_unsampleable_layers(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: _app([_layer("a"), _layer("b")])

        def fake_probe(_app, name, **_kwargs):
            if name == "a":
                return {"layer": "a", "status": "ok", "no_op": True, "reason": "invisible"}
            return {"layer": "b", "status": "unsupported", "no_op": None, "reason": "no pixels"}

        module.probe_layer_effect = fake_probe

        result = module.verify_layer_batch()

        warning = result["context"]["warning"]
        assert "1 layer(s) do not change the composite: a" in warning
        assert "1 layer(s) could not be sampled: b" in warning
        assert result["context"]["inconclusive_layers"] == ["b"]
        # Only a measured no-op is actionable; an unsampleable layer is not
        # reported as one.
        assert result["context"]["no_op_layers"] == ["a"]

    def test_missing_layers_are_called_out(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: _app([])

        result = module.verify_layer_batch(layers=["ghost"])

        assert result["context"]["missing_layers"] == ["ghost"]
        assert "not found: ghost" in result["context"]["warning"]

    def test_no_active_document_reports_an_error(self):
        module = _load_script("verify_layer_batch.py")
        module.Photoshop = lambda: Mock(activeDocument=None)

        result = module.verify_layer_batch()

        assert result["context"]["error"] == "No active document"


class TestSetLayerBlendModeVerification:
    def test_overlay_on_white_is_surfaced_as_a_no_op(self):
        module = _load_script("set_layer_blend_mode.py")
        module.Photoshop = lambda: _app([_layer("batch_04")])
        module.probe_layer_effect = _scripted_probe({"batch_04": WHITE})

        result = module.set_layer_blend_mode(name="batch_04", blend_mode="overlay")

        assert result["success"] is True
        assert result["context"]["blend_mode"] == "overlay"
        assert result["context"]["no_op"] is True
        assert result["context"]["warning"]
        assert result["context"]["effect"]["max_delta"] == 0.0
        assert result["context"]["effect"]["status"] == "ok"

    def test_visible_layer_reports_no_warning(self):
        module = _load_script("set_layer_blend_mode.py")
        module.Photoshop = lambda: _app([_layer("batch_01")])
        module.probe_layer_effect = _scripted_probe({"batch_01": BLUE})

        result = module.set_layer_blend_mode(name="batch_01", blend_mode="multiply")

        assert result["context"]["no_op"] is False
        assert result["context"]["warning"] is None
        assert result["context"]["effect"]["max_delta"] == 227.0

    def test_verify_false_skips_the_readback(self):
        module = _load_script("set_layer_blend_mode.py")
        module.Photoshop = lambda: _app([_layer("batch_04")])
        module.probe_layer_effect = _verification_must_not_run

        result = module.set_layer_blend_mode(name="batch_04", blend_mode="overlay", verify=False)

        assert result["success"] is True
        assert result["context"]["blend_mode"] == "overlay"
        assert "effect" not in result["context"]

    def test_verification_is_enabled_by_default(self):
        module = _load_script("set_layer_blend_mode.py")
        module.Photoshop = lambda: _app([_layer("batch_04")])
        module.probe_layer_effect = _scripted_probe({"batch_04": WHITE})

        result = module.set_layer_blend_mode(name="batch_04", blend_mode="overlay")

        assert "effect" in result["context"]


class TestSetLayerOpacityVerification:
    def test_zero_effective_contribution_is_surfaced(self):
        module = _load_script("set_layer_opacity.py")
        module.Photoshop = lambda: _app([_layer("batch_04")])
        module.probe_layer_effect = _scripted_probe({"batch_04": WHITE})

        result = module.set_layer_opacity(name="batch_04", opacity=76)

        assert result["context"]["opacity"] == 76
        assert result["context"]["no_op"] is True
        assert result["context"]["warning"]

    def test_visible_layer_reports_no_warning(self):
        module = _load_script("set_layer_opacity.py")
        module.Photoshop = lambda: _app([_layer("batch_01")])
        module.probe_layer_effect = _scripted_probe({"batch_01": BLUE})

        result = module.set_layer_opacity(name="batch_01", opacity=92)

        assert result["context"]["no_op"] is False
        assert result["context"]["warning"] is None

    def test_verify_false_skips_the_readback(self):
        module = _load_script("set_layer_opacity.py")
        module.Photoshop = lambda: _app([_layer("batch_04")])
        module.probe_layer_effect = _verification_must_not_run

        result = module.set_layer_opacity(name="batch_04", opacity=0, verify=False)

        assert result["success"] is True
        assert result["context"]["opacity"] == 0
        assert "effect" not in result["context"]


@pytest.mark.parametrize("script", ["set_layer_blend_mode.py", "set_layer_opacity.py"])
def test_setters_still_apply_the_change_when_verification_runs(script):
    """The write must happen regardless of what the probe reports."""
    module = _load_script(script)
    app = _app([_layer("batch_01")])
    module.Photoshop = lambda: app
    module.probe_layer_effect = _scripted_probe({"batch_01": BLUE})

    if "blend_mode" in script:
        module.set_layer_blend_mode(name="batch_01", blend_mode="multiply")
        expected = {"_obj": "set", "_target": [{"_ref": "layer", "_name": "batch_01"}]}
    else:
        module.set_layer_opacity(name="batch_01", opacity=50)
        expected = {"_obj": "set", "_target": [{"_ref": "layer", "_name": "batch_01"}]}

    write = app.batch_play.call_args_list[0].args[0][0]
    assert write["_obj"] == expected["_obj"]
    assert write["_target"] == expected["_target"]
