"""Composite-effect probing for Adobe Photoshop layers.

A layer property change can be a *mathematical* no-op: ``OVERLAY`` blended over
a solid white backdrop evaluates to exactly white again, so the layer vanishes
from the composite while every layer property still reports the value the caller
asked for.  Batch flows then produce documents that look successful and are
silently missing content, and the loss is only discovered downstream.

This module turns that silent no-op into a measurable signal.  It samples the
**composite** (not the layer's own pixels) at a grid of points inside the
layer's bounds, once with the layer shown and once with it hidden, and compares
the two.  A layer whose contribution is zero everywhere is reported as
``no_op``.

Only :func:`read_composite_colors` talks to Photoshop.  Everything else is pure
Python so the decision logic can be unit tested without a Photoshop instance.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

# Default number of sample points per axis inside a layer's bounds.  Three
# gives a 3x3 grid: enough to survive a hole in the middle of a layer without
# making every single-layer call expensive.
DEFAULT_PER_AXIS = 3

# A per-channel composite delta at or below this value (0-255 scale) counts as
# "no visible effect".  Non-zero because Photoshop rounds 8-bit composites.
DEFAULT_TOLERANCE = 1.0

# Verdict statuses.
STATUS_OK = "ok"
STATUS_HIDDEN = "hidden"
STATUS_MISSING = "missing"
STATUS_NO_BOUNDS = "no_bounds"
STATUS_EMPTY = "empty"
STATUS_UNSUPPORTED = "unsupported"
STATUS_ERROR = "error"

# Statuses where the probe could not say anything about the composite.  These
# must never reach the actionable no-op list: "we could not tell" is not the
# same claim as "we measured it and it does nothing".
_INCONCLUSIVE = (STATUS_UNSUPPORTED, STATUS_ERROR, STATUS_MISSING, STATUS_NO_BOUNDS)


class EffectProbeUnavailable(RuntimeError):
    """Raised when composite pixels cannot be read from the host."""


# UXP source for :func:`read_composite_colors`.  ``__POINTS__`` is replaced
# with a JSON array of ``[x, y]`` pairs.  The script is deliberately
# synchronous (the UXP Photoshop DOM is synchronous) and returns a plain
# ``{colors: [...]}`` / ``{error: "..."}`` object instead of throwing, so a
# Photoshop build without colour-sampler support degrades into a structured
# error rather than a broken tool.
_SAMPLER_JS = """(function () {
  var POINTS = __POINTS__;
  try {
    var ps = require("photoshop");
    var doc = ps.app.activeDocument;
    if (!doc) { return { error: "no-active-document" }; }
    var samplers = doc.colorSamplers;
    if (!samplers || typeof samplers.add !== "function") {
      return { error: "color-samplers-unavailable" };
    }
    var colors = [];
    for (var i = 0; i < POINTS.length; i++) {
      var point = POINTS[i];
      var sampler = samplers.add([point[0], point[1]]);
      var rgb = null;
      try {
        var color = sampler.color;
        if (color && color.rgb) {
          rgb = [color.rgb.red, color.rgb.green, color.rgb.blue];
        }
      } finally {
        if (sampler && typeof sampler.remove === "function") { sampler.remove(); }
      }
      if (!rgb) { return { error: "sampler-color-unavailable" }; }
      colors.push(rgb);
    }
    return { colors: colors };
  } catch (error) {
    return { error: String((error && error.message) || error) };
  }
})()"""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def grid_points(
    bounds: Mapping[str, float],
    per_axis: int = DEFAULT_PER_AXIS,
    limit: Optional[Tuple[float, float]] = None,
) -> List[Tuple[float, float]]:
    """Return ``per_axis ** 2`` points evenly spread inside ``bounds``.

    Args:
        bounds: Mapping with ``left``, ``top``, ``right`` and ``bottom`` edges in
            document pixels.
        per_axis: Number of sample points along each axis.
        limit: Optional ``(width, height)`` of the document; points are clamped
            inside it so a layer that hangs off the canvas stays sampleable.

    Returns:
        List of ``(x, y)`` pairs, ordered row-major.

    Raises:
        ValueError: If ``bounds`` describes an empty or invalid region.
    """
    try:
        left = float(bounds["left"])
        top = float(bounds["top"])
        right = float(bounds["right"])
        bottom = float(bounds["bottom"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid layer bounds: {bounds!r}") from exc

    if right <= left or bottom <= top:
        raise ValueError(f"layer bounds have no area: {bounds!r}")

    count = max(1, int(per_axis))
    points: List[Tuple[float, float]] = []
    for row in range(count):
        for column in range(count):
            x = left + (right - left) * (column + 0.5) / count
            y = top + (bottom - top) * (row + 0.5) / count
            if limit is not None:
                width, height = limit
                x = min(max(x, 0.0), max(float(width) - 1.0, 0.0))
                y = min(max(y, 0.0), max(float(height) - 1.0, 0.0))
            points.append((x, y))
    return points


def channel_delta(first: Sequence[float], second: Sequence[float]) -> float:
    """Return the largest per-channel difference between two RGB samples."""
    return max(
        (abs(float(a) - float(b)) for a, b in zip(tuple(first)[:3], tuple(second)[:3])),
        default=0.0,
    )


def build_samples(
    points: Sequence[Tuple[float, float]],
    with_layer: Sequence[Sequence[float]],
    without_layer: Sequence[Sequence[float]],
) -> List[Dict[str, Any]]:
    """Pair up sample coordinates with their two composite readings."""
    samples: List[Dict[str, Any]] = []
    for index, point in enumerate(points):
        shown = list(with_layer[index]) if index < len(with_layer) else []
        hidden = list(without_layer[index]) if index < len(without_layer) else []
        samples.append(
            {
                "x": round(float(point[0]), 2),
                "y": round(float(point[1]), 2),
                "with_layer": shown,
                "without_layer": hidden,
                "delta": round(channel_delta(shown, hidden), 3),
            }
        )
    return samples


def summarise(samples: Sequence[Mapping[str, Any]], tolerance: float = DEFAULT_TOLERANCE) -> Dict[str, Any]:
    """Reduce per-point deltas into a ``no_op`` verdict.

    Args:
        samples: Output of :func:`build_samples`.
        tolerance: Largest per-channel delta (0-255) still counted as invisible.

    Returns:
        Dict with ``max_delta``, ``mean_delta``, ``tolerance`` and ``no_op``.
    """
    deltas = [float(sample.get("delta", 0.0)) for sample in samples]
    if not deltas:
        return {"max_delta": 0.0, "mean_delta": 0.0, "tolerance": tolerance, "no_op": True}
    max_delta = max(deltas)
    return {
        "max_delta": round(max_delta, 3),
        "mean_delta": round(sum(deltas) / len(deltas), 3),
        "tolerance": tolerance,
        "no_op": max_delta <= tolerance,
    }


def is_inconclusive(status: str) -> bool:
    """True when the probe could not determine the composite contribution."""
    return status in _INCONCLUSIVE


def build_effect(
    layer: str,
    status: str,
    reason: str,
    *,
    samples: Optional[Sequence[Mapping[str, Any]]] = None,
    tolerance: float = DEFAULT_TOLERANCE,
    visibility_restored: bool = True,
) -> Dict[str, Any]:
    """Assemble the per-layer effect report returned by the tools."""
    sample_list = list(samples or [])
    effect: Dict[str, Any] = {
        "layer": layer,
        "status": status,
        "no_op": None,
        "visibility_restored": visibility_restored,
        "reason": reason,
        "sample_count": len(sample_list),
    }
    if status in _INCONCLUSIVE:
        # Conclusive "unknown" beats a silent false negative.
        effect["samples"] = sample_list
        return effect
    if status != STATUS_OK:
        # Hidden layers and zero-area layers genuinely contribute nothing.
        effect["no_op"] = True
        effect["samples"] = sample_list
        return effect
    effect.update(summarise(sample_list, tolerance))
    effect["samples"] = sample_list
    return effect


# ---------------------------------------------------------------------------
# Photoshop access
# ---------------------------------------------------------------------------


def read_composite_colors(app: Any, points: Sequence[Tuple[float, float]]) -> List[List[float]]:
    """Read the composited RGB at ``points`` from the active document.

    Args:
        app: Connected :class:`adobe.photoshop.Photoshop` session.
        points: ``(x, y)`` document coordinates.

    Returns:
        One ``[r, g, b]`` triple per point, in the same order.

    Raises:
        EffectProbeUnavailable: If the host cannot provide composite pixels.
    """
    payload = [[round(float(x), 3), round(float(y), 3)] for x, y in points]
    source = _SAMPLER_JS.replace("__POINTS__", json.dumps(payload))
    try:
        raw = app.eval_js(source)
    except Exception as exc:  # noqa: BLE001 - host transport errors vary
        raise EffectProbeUnavailable(str(exc)) from exc
    return _parse_colors(raw, len(payload))


def _parse_colors(raw: Any, expected: int) -> List[List[float]]:
    """Normalise the ``evalJs`` payload into RGB triples."""
    payload = raw
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise EffectProbeUnavailable(f"host returned non-JSON probe result: {raw!r}") from exc
    if not isinstance(payload, Mapping):
        raise EffectProbeUnavailable(f"unexpected probe result type: {type(raw).__name__}")
    error = payload.get("error")
    if error:
        raise EffectProbeUnavailable(str(error))
    colors = payload.get("colors")
    if not isinstance(colors, list) or len(colors) != expected:
        raise EffectProbeUnavailable(
            f"probe returned {len(colors) if isinstance(colors, list) else 0}/{expected} colors"
        )
    parsed: List[List[float]] = []
    for triple in colors:
        try:
            parsed.append([float(triple[0]), float(triple[1]), float(triple[2])])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise EffectProbeUnavailable(f"unreadable probe color: {triple!r}") from exc
    return parsed


# Guard against a host that reports a cyclic layer tree.
MAX_LAYER_DEPTH = 32


def iter_layers(layers: Any, depth: int = 0) -> Iterator[Any]:
    """Yield ``layers`` and every nested descendant, depth-first.

    A batch is not necessarily flat. Scanning only the top level would report
    layers inside a group as missing, which makes an unchecked batch look
    clean rather than uncovered.
    """
    if depth > MAX_LAYER_DEPTH or not isinstance(layers, Iterable):
        return
    for layer in layers:
        yield layer
        yield from iter_layers(getattr(layer, "layers", None), depth + 1)


def find_layer(app: Any, name: str) -> Optional[Any]:
    """Return the named layer proxy from the active document, if present."""
    document = getattr(app, "activeDocument", None)
    if document is None:
        return None
    for layer in iter_layers(getattr(document, "layers", None)):
        if getattr(layer, "name", None) == name:
            return layer
    return None


def layer_bounds(app: Any, name: str) -> Optional[Dict[str, float]]:
    """Return ``{left, top, right, bottom}`` for ``name`` in document pixels."""
    try:
        result = app.batch_play(
            [
                {
                    "_obj": "get",
                    "_target": [{"_ref": "property", "_property": "bounds"}, {"_ref": "layer", "_name": name}],
                }
            ],
            modal=True,
            command_name="Get layer bounds",
        )
    except Exception:  # noqa: BLE001 - a missing/unsupported probe must not abort the caller
        return None

    payload = result[0] if isinstance(result, list) and result else result
    bounds = payload.get("bounds") if isinstance(payload, Mapping) else None
    if not isinstance(bounds, Mapping):
        return None
    try:
        return {key: float(bounds[key]) for key in ("left", "top", "right", "bottom")}
    except (KeyError, TypeError, ValueError):
        return None


def set_layer_visibility(app: Any, name: str, visible: bool) -> None:
    """Show or hide a layer by name."""
    action = "show" if visible else "hide"
    app.batch_play(
        [{"_obj": action, "_target": [{"_ref": "layer", "_name": name}]}],
        modal=True,
        command_name=f"{'Show' if visible else 'Hide'} layer",
    )


def _restore_visibility(app: Any, name: str) -> Optional[str]:
    """Show a layer again, returning an error message instead of raising.

    The probe's only write to the document is hiding a layer, so a failed
    restore has to be surfaced rather than swallowed.
    """
    try:
        set_layer_visibility(app, name, True)
    except Exception as exc:  # noqa: BLE001 - reported by the caller
        return str(exc)
    return None


def document_size(app: Any) -> Optional[Tuple[float, float]]:
    """Return ``(width, height)`` of the active document in pixels, if known."""
    document = getattr(app, "activeDocument", None)
    if document is None:
        return None
    try:
        return float(document.width), float(document.height)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def probe_layer_effect(
    app: Any,
    name: str,
    *,
    per_axis: int = DEFAULT_PER_AXIS,
    tolerance: float = DEFAULT_TOLERANCE,
    sampler: Optional[Callable[[Any, Sequence[Tuple[float, float]]], List[List[float]]]] = None,
) -> Dict[str, Any]:
    """Measure how much a layer contributes to the composite.

    The layer is sampled, hidden, sampled again and then restored.  Visibility
    is restored in a ``finally`` block so a failed probe can never leave the
    document with a hidden layer.

    Args:
        app: Connected :class:`adobe.photoshop.Photoshop` session.
        name: Exact layer name.
        per_axis: Sample points per axis inside the layer bounds.
        tolerance: Largest per-channel delta still counted as invisible.
        sampler: Injection point for tests; defaults to
            :func:`read_composite_colors`.

    Returns:
        A per-layer effect report from :func:`build_effect`.
    """
    read = sampler or read_composite_colors

    layer = find_layer(app, name)
    if layer is None:
        return build_effect(name, STATUS_MISSING, f"layer '{name}' was not found in the active document")
    if not getattr(layer, "visible", True):
        return build_effect(
            name,
            STATUS_HIDDEN,
            f"layer '{name}' is hidden, so it cannot affect the composite until it is shown again",
        )

    bounds = layer_bounds(app, name)
    if bounds is None:
        return build_effect(
            name,
            STATUS_NO_BOUNDS,
            f"could not read bounds for '{name}', so its composite contribution is unknown",
        )

    try:
        points = grid_points(bounds, per_axis, document_size(app))
    except ValueError as exc:
        # Zero-area bounds: there is nowhere for this layer to change anything.
        return build_effect(name, STATUS_EMPTY, str(exc))

    try:
        with_layer = read(app, points)
    except EffectProbeUnavailable as exc:
        return build_effect(name, STATUS_UNSUPPORTED, f"composite pixels unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001 - never break the caller's own operation
        return build_effect(name, STATUS_ERROR, f"composite probe failed: {exc}")

    try:
        set_layer_visibility(app, name, False)
    except Exception as exc:  # noqa: BLE001 - never break the caller's own operation
        return build_effect(name, STATUS_ERROR, f"could not hide '{name}' to measure the baseline: {exc}")

    probe_error: Optional[Tuple[str, str]] = None
    without_layer: List[List[float]] = []
    try:
        without_layer = read(app, points)
    except EffectProbeUnavailable as exc:
        probe_error = (STATUS_UNSUPPORTED, f"composite pixels unavailable: {exc}")
    except Exception as exc:  # noqa: BLE001
        probe_error = (STATUS_ERROR, f"composite probe failed: {exc}")
    finally:
        # Always attempt the restore; a layer left hidden is the one side
        # effect this probe can leave behind, so it gets its own verdict.
        restore_error = _restore_visibility(app, name)

    if restore_error:
        return build_effect(
            name,
            STATUS_ERROR,
            f"'{name}' could not be shown again ({restore_error}); it may still be hidden",
            visibility_restored=False,
        )
    if probe_error:
        return build_effect(name, probe_error[0], probe_error[1])

    samples = build_samples(points, with_layer, without_layer)
    effect = build_effect(name, STATUS_OK, "", samples=samples, tolerance=tolerance)
    if effect["no_op"]:
        effect["reason"] = (
            f"'{name}' changes the composite by at most {effect['max_delta']}/255; "
            "its current blend mode and opacity evaluate to the backdrop underneath"
        )
    else:
        effect["reason"] = f"'{name}' changes the composite by up to {effect['max_delta']}/255"
    return effect
