"""Tests for composite-effect probing used to expose silent layer no-ops.

Everything except :func:`read_composite_colors` is pure Python, so the decision
logic is covered here without a Photoshop instance.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from dcc_mcp_photoshop._layer_effect import (
    DEFAULT_TOLERANCE,
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_HIDDEN,
    STATUS_MISSING,
    STATUS_NO_BOUNDS,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    EffectProbeUnavailable,
    build_samples,
    channel_delta,
    document_size,
    find_layer,
    grid_points,
    is_inconclusive,
    iter_layers,
    layer_bounds,
    probe_layer_effect,
    read_composite_colors,
    summarise,
)

WHITE = [255.0, 255.0, 255.0]
BLUE = [28.0, 38.0, 66.0]

# batch_04 from the reported reproduction: OVERLAY over solid white.
NOOP_WITH = [WHITE] * 9
NOOP_WITHOUT = [WHITE] * 9
# batch_01: the layer is clearly visible.
VISIBLE_WITH = [BLUE] * 9
VISIBLE_WITHOUT = [WHITE] * 9


def _layer(name="Layer 1", visible=True, bounds=None):
    layer = Mock()
    layer.name = name
    layer.visible = visible
    layer.bounds = bounds
    return layer


def _app(layers=None, width=1200, height=800):
    app = Mock()
    document = Mock()
    document.layers = layers if layers is not None else [_layer()]
    document.width = width
    document.height = height
    app.activeDocument = document
    return app


class TestGridPoints:
    def test_three_by_three_grid_lands_inside_bounds(self):
        points = grid_points({"left": 0, "top": 0, "right": 90, "bottom": 90}, per_axis=3)

        assert len(points) == 9
        x_values = sorted({x for x, _ in points})
        assert x_values == [15.0, 45.0, 75.0]

    def test_single_point_is_the_centre(self):
        points = grid_points({"left": 100, "top": 200, "right": 300, "bottom": 400}, per_axis=1)

        assert points == [(200.0, 300.0)]

    def test_points_are_clamped_into_the_canvas(self):
        # A layer hanging off the right/bottom edge must stay sampleable.
        points = grid_points(
            {"left": 1190, "top": 790, "right": 1210, "bottom": 810},
            per_axis=1,
            limit=(1200, 800),
        )

        assert points == [(1199.0, 799.0)]

    def test_empty_bounds_are_rejected(self):
        with pytest.raises(ValueError, match="no area"):
            grid_points({"left": 10, "top": 10, "right": 10, "bottom": 50})

    def test_missing_edges_are_rejected(self):
        with pytest.raises(ValueError, match="invalid layer bounds"):
            grid_points({"left": 0, "top": 0, "right": 10})


class TestChannelDelta:
    def test_identical_samples_have_no_delta(self):
        assert channel_delta(WHITE, WHITE) == 0.0

    def test_delta_is_the_largest_channel_gap(self):
        assert channel_delta([10, 200, 30], [12, 190, 31]) == 10.0

    def test_short_samples_do_not_raise(self):
        assert channel_delta([1], []) == 0.0


class TestBuildSamples:
    def test_pairs_points_with_both_readings(self):
        points = [(1.0, 2.0), (3.0, 4.0)]

        samples = build_samples(points, [WHITE, BLUE], [BLUE, BLUE])

        assert [sample["x"] for sample in samples] == [1.0, 3.0]
        assert samples[0]["delta"] == 227.0
        assert samples[1]["delta"] == 0.0

    def test_missing_reading_counts_as_no_effect(self):
        samples = build_samples([(0.0, 0.0)], [], [])

        assert samples[0]["delta"] == 0.0


class TestSummarise:
    def test_zero_deltas_are_a_no_op(self):
        samples = build_samples([(0.0, 0.0)] * 9, NOOP_WITH, NOOP_WITHOUT)

        result = summarise(samples)

        assert result["no_op"] is True
        assert result["max_delta"] == 0.0
        assert result["mean_delta"] == 0.0

    def test_large_deltas_are_not_a_no_op(self):
        samples = build_samples([(0.0, 0.0)] * 9, VISIBLE_WITH, VISIBLE_WITHOUT)

        result = summarise(samples)

        assert result["no_op"] is False
        assert result["max_delta"] == 227.0

    def test_tolerance_is_exclusive_boundary(self):
        samples = build_samples([(0.0, 0.0)], [[1.0, 1.0, 1.0]], [[0.0, 0.0, 0.0]])
        # Rounded 8-bit composites can legitimately differ by a hair.
        assert summarise(samples, tolerance=1.0)["no_op"] is True
        assert summarise(samples, tolerance=0.5)["no_op"] is False

    def test_no_samples_is_treated_as_a_no_op(self):
        assert summarise([])["no_op"] is True


class TestReadCompositeColors:
    def test_points_are_embedded_as_json_and_results_returned(self):
        app = Mock()
        app.eval_js.return_value = {"colors": [[1, 2, 3], [4, 5, 6]]}

        colors = read_composite_colors(app, [(10.5, 20.25), (30.0, 40.0)])

        assert colors == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        source = app.eval_js.call_args.args[0]
        assert "[[10.5, 20.25], [30.0, 40.0]]" in source

    def test_string_payload_is_json_decoded(self):
        app = Mock()
        app.eval_js.return_value = '{"colors": [[255, 255, 255]]}'

        assert read_composite_colors(app, [(0.0, 0.0)]) == [[255.0, 255.0, 255.0]]

    def test_structured_host_error_is_unavailable(self):
        app = Mock()
        app.eval_js.return_value = {"error": "color-samplers-unavailable"}

        with pytest.raises(EffectProbeUnavailable, match="color-samplers-unavailable"):
            read_composite_colors(app, [(0.0, 0.0)])

    def test_transport_failure_is_unavailable(self):
        app = Mock()
        app.eval_js.side_effect = RuntimeError("broker unreachable")

        with pytest.raises(EffectProbeUnavailable, match="broker unreachable"):
            read_composite_colors(app, [(0.0, 0.0)])

    def test_wrong_sample_count_is_unavailable(self):
        app = Mock()
        app.eval_js.return_value = {"colors": [[1, 2, 3]]}

        with pytest.raises(EffectProbeUnavailable, match="1/2 colors"):
            read_composite_colors(app, [(0.0, 0.0), (1.0, 1.0)])

    def test_non_json_payload_is_unavailable(self):
        app = Mock()
        app.eval_js.return_value = "not json"

        with pytest.raises(EffectProbeUnavailable, match="non-JSON"):
            read_composite_colors(app, [(0.0, 0.0)])


class TestHostAccess:
    def test_find_layer_matches_by_name(self):
        app = _app([_layer("Background"), _layer("batch_04")])

        assert find_layer(app, "batch_04").name == "batch_04"

    def test_find_layer_returns_none_when_absent(self):
        assert find_layer(_app(), "nope") is None

    def test_find_layer_without_document(self):
        assert find_layer(Mock(activeDocument=None), "x") is None

    def test_find_layer_walks_into_groups(self):
        child = _layer("nested")
        child.layers = []
        group = _layer("Group 1")
        group.layers = [child]

        assert find_layer(_app([_layer("Top"), group]), "nested") is child


class TestIterLayers:
    def test_flattens_nested_groups(self):
        child = _layer("child")
        child.layers = []
        group = _layer("group")
        group.layers = [child]
        top = _layer("top")
        top.layers = []

        assert [layer.name for layer in iter_layers([top, group])] == ["top", "group", "child"]

    def test_accepts_none(self):
        assert list(iter_layers(None)) == []

    def test_terminates_on_a_cyclic_tree(self):
        # A host reporting a cycle must not hang the caller.
        cyclic = _layer("loop")
        cyclic.layers = [cyclic]

        names = [layer.name for layer in iter_layers([cyclic])]

        assert len(names) <= 33

    def test_layer_bounds_parses_the_get_descriptor(self):
        app = Mock()
        app.batch_play.return_value = [{"bounds": {"top": 411, "left": 94, "bottom": 520, "right": 1106}}]

        assert layer_bounds(app, "batch_04") == {
            "left": 94.0,
            "top": 411.0,
            "right": 1106.0,
            "bottom": 520.0,
        }

        app.batch_play.assert_called_once_with(
            [
                {
                    "_obj": "get",
                    "_target": [
                        {"_ref": "property", "_property": "bounds"},
                        {"_ref": "layer", "_name": "batch_04"},
                    ],
                }
            ],
            modal=True,
            command_name="Get layer bounds",
        )

    def test_layer_bounds_returns_none_when_unreadable(self):
        app = Mock()
        app.batch_play.return_value = [{}]

        assert layer_bounds(app, "batch_04") is None

    def test_layer_bounds_swallows_host_errors(self):
        app = Mock()
        app.batch_play.side_effect = RuntimeError("boom")

        assert layer_bounds(app, "batch_04") is None

    def test_document_size(self):
        assert document_size(_app()) == (1200.0, 800.0)

    def test_document_size_is_none_without_a_document(self):
        assert document_size(Mock(activeDocument=None)) is None


class TestProbeLayerEffect:
    @staticmethod
    def _sampler(with_colors, without_colors):
        """Return a sampler that reads ``with_colors`` then ``without_colors``."""
        calls = {"count": 0}

        def sampler(_app, points):
            calls["count"] += 1
            colors = with_colors if calls["count"] == 1 else without_colors
            assert len(colors) == len(points)
            return [list(color) for color in colors]

        return sampler

    def test_no_op_layer_is_reported(self):
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],  # bounds
            None,  # hide
            None,  # show
        ]

        effect = probe_layer_effect(
            app,
            "batch_04",
            sampler=self._sampler(NOOP_WITH, NOOP_WITHOUT),
        )

        assert effect["status"] == STATUS_OK
        assert effect["no_op"] is True
        assert effect["max_delta"] == 0.0
        assert effect["sample_count"] == 9
        assert "changes the composite by at most" in effect["reason"]

    def test_visible_layer_is_not_a_no_op(self):
        app = _app([_layer("batch_01")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],
            None,
            None,
        ]

        effect = probe_layer_effect(
            app,
            "batch_01",
            sampler=self._sampler(VISIBLE_WITH, VISIBLE_WITHOUT),
        )

        assert effect["status"] == STATUS_OK
        assert effect["no_op"] is False
        assert effect["max_delta"] == 227.0
        assert "up to 227.0/255" in effect["reason"]

    def test_visibility_is_always_restored(self):
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],
            None,  # hide
            None,  # show
        ]

        probe_layer_effect(app, "batch_04", sampler=self._sampler(NOOP_WITH, NOOP_WITHOUT))

        hidden, shown = app.batch_play.call_args_list[1], app.batch_play.call_args_list[2]
        assert hidden.args[0][0]["_obj"] == "hide"
        assert shown.args[0][0]["_obj"] == "show"

    def test_visibility_is_restored_even_when_the_probe_raises(self):
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],
            None,  # hide
            None,  # show
        ]
        calls = {"count": 0}

        def exploding_sampler(_app, points):
            calls["count"] += 1
            if calls["count"] == 1:
                return [list(WHITE) for _ in points]
            raise EffectProbeUnavailable("sampler exploded")

        effect = probe_layer_effect(app, "batch_04", sampler=exploding_sampler)

        assert effect["status"] == STATUS_UNSUPPORTED
        assert effect["no_op"] is None
        assert effect["visibility_restored"] is True
        assert app.batch_play.call_args_list[-1].args[0][0]["_obj"] == "show"

    def test_restore_failure_is_reported_not_swallowed(self):
        # Hiding is the probe's only write; a failure to undo it must surface.
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],  # bounds
            None,  # hide succeeds
            RuntimeError("show failed"),  # restore fails
        ]

        effect = probe_layer_effect(
            app,
            "batch_04",
            sampler=self._sampler(NOOP_WITH, NOOP_WITHOUT),
        )

        assert effect["status"] == STATUS_ERROR
        assert effect["no_op"] is None
        assert effect["visibility_restored"] is False
        assert "could not be shown again" in effect["reason"]
        assert "show failed" in effect["reason"]

    def test_restore_failure_wins_over_a_clean_no_op_verdict(self):
        # The samples say "invisible", but the document is now wrong; the
        # dangerous state has to take precedence over the tidy verdict.
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],
            None,
            RuntimeError("show failed"),
        ]

        effect = probe_layer_effect(
            app,
            "batch_04",
            sampler=self._sampler(VISIBLE_WITH, VISIBLE_WITHOUT),
        )

        assert effect["status"] == STATUS_ERROR
        assert effect["visibility_restored"] is False

    def test_hide_failure_is_reported_and_needs_no_restore(self):
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}],
            RuntimeError("hide failed"),  # hide fails
        ]

        effect = probe_layer_effect(
            app,
            "batch_04",
            sampler=self._sampler(NOOP_WITH, NOOP_WITHOUT),
        )

        assert effect["status"] == STATUS_ERROR
        assert effect["no_op"] is None
        assert effect["visibility_restored"] is True
        assert "could not hide" in effect["reason"]
        # Nothing was hidden, so no show must be attempted.
        assert app.batch_play.call_count == 2

    def test_unreadable_pixels_are_inconclusive_not_a_false_no_op(self):
        app = _app([_layer("batch_04")])
        app.batch_play.return_value = [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}]

        def broken_sampler(_app, _points):
            raise EffectProbeUnavailable("color-samplers-unavailable")

        effect = probe_layer_effect(app, "batch_04", sampler=broken_sampler)

        assert effect["status"] == STATUS_UNSUPPORTED
        assert effect["no_op"] is None
        assert "color-samplers-unavailable" in effect["reason"]

    def test_unexpected_probe_failure_is_reported(self):
        app = _app([_layer("batch_04")])
        app.batch_play.return_value = [{"bounds": {"left": 0, "top": 0, "right": 9, "bottom": 9}}]

        def broken_sampler(_app, _points):
            raise RuntimeError("unexpected")

        effect = probe_layer_effect(app, "batch_04", sampler=broken_sampler)

        assert effect["status"] == STATUS_ERROR
        assert effect["no_op"] is None

    def test_hidden_layer_is_reported_as_a_no_op(self):
        app = _app([_layer("batch_04", visible=False)])

        effect = probe_layer_effect(app, "batch_04")

        assert effect["status"] == STATUS_HIDDEN
        assert effect["no_op"] is True
        assert effect["visibility_restored"] is True
        assert "hidden" in effect["reason"]
        # No sampling needed once the layer is known to be hidden.
        assert effect["sample_count"] == 0

    def test_hidden_layer_is_a_measured_verdict(self):
        # A hidden layer genuinely affects nothing, so it stays actionable.
        assert is_inconclusive(STATUS_HIDDEN) is False

    def test_missing_layer_is_reported(self):
        effect = probe_layer_effect(_app(), "nope")

        assert effect["status"] == STATUS_MISSING
        assert effect["no_op"] is None

    def test_unreadable_bounds_are_inconclusive_not_a_no_op(self):
        # A layer we could not measure must never be reported as "invisible",
        # otherwise the caller is told to fix a layer that may be fine.
        app = _app([_layer("batch_04")])
        app.batch_play.return_value = [{}]

        effect = probe_layer_effect(app, "batch_04")

        assert effect["status"] == STATUS_NO_BOUNDS
        assert effect["no_op"] is None
        assert effect["visibility_restored"] is True
        assert "unknown" in effect["reason"]

    def test_unreadable_bounds_are_inconclusive(self):
        assert is_inconclusive(STATUS_NO_BOUNDS) is True
        assert is_inconclusive(STATUS_UNSUPPORTED) is True
        assert is_inconclusive(STATUS_ERROR) is True
        assert is_inconclusive(STATUS_MISSING) is True

    def test_measured_statuses_are_not_inconclusive(self):
        assert is_inconclusive(STATUS_OK) is False
        assert is_inconclusive(STATUS_HIDDEN) is False
        assert is_inconclusive(STATUS_EMPTY) is False

    def test_zero_area_bounds_are_a_measured_no_op(self):
        # Nothing to sample is a real answer, unlike "bounds unavailable".
        app = _app([_layer("batch_04")])
        app.batch_play.return_value = [{"bounds": {"left": 5, "top": 5, "right": 5, "bottom": 50}}]

        effect = probe_layer_effect(app, "batch_04")

        assert effect["status"] == STATUS_EMPTY
        assert effect["no_op"] is True
        assert "no area" in effect["reason"]

    def test_default_tolerance_is_applied(self):
        app = _app([_layer("batch_04")])
        app.batch_play.side_effect = [
            [{"bounds": {"left": 0, "top": 0, "right": 2, "bottom": 2}}],
            None,
            None,
        ]
        # A one-step 8-bit rounding difference must not be called invisible.
        nearly = [[1.0, 1.0, 1.0]]
        black = [[0.0, 0.0, 0.0]]

        effect = probe_layer_effect(app, "batch_04", per_axis=1, sampler=self._sampler(nearly, black))

        assert effect["tolerance"] == DEFAULT_TOLERANCE
        assert effect["no_op"] is True
