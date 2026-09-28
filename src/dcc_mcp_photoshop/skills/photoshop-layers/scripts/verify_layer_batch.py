"""Report which layers contribute nothing to the Photoshop composite.

Batch layer operations can succeed silently while producing a layer that is
mathematically invisible: ``OVERLAY`` over a solid white backdrop evaluates to
exactly white again, and a hidden or fully transparent layer contributes
nothing either.  Each individual write still reports success, so the loss is
only discovered downstream.

This tool answers one question for a whole batch at once: *for each of these
layers, does the composite change at all when the layer is hidden?*
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._layer_effect import (
    DEFAULT_PER_AXIS,
    DEFAULT_TOLERANCE,
    STATUS_ERROR,
    STATUS_MISSING,
    STATUS_UNSUPPORTED,
    probe_layer_effect,
)

_INCONCLUSIVE = (STATUS_UNSUPPORTED, STATUS_ERROR)


@skill_entry
def verify_layer_batch(
    layers: Optional[Sequence[str]] = None,
    per_axis: int = DEFAULT_PER_AXIS,
    tolerance: float = DEFAULT_TOLERANCE,
    **kwargs,
) -> dict:
    """Verify that a batch of layers actually shows up in the composite.

    Args:
        layers: Layer names to check. Defaults to every top-level layer of the
            active document.
        per_axis: Composite sample points per axis inside each layer's bounds
            (``per_axis ** 2`` samples in total).
        tolerance: Largest per-channel composite delta (0-255) still reported
            as invisible.

    Returns:
        dict: ActionResultModel with a ``per_layer`` report per checked layer
        plus the ``no_op_layers`` summary. Each report carries ``status``,
        ``no_op``, ``max_delta`` and a human-readable ``reason``.
    """
    app = Photoshop()

    return action_result(
        "Verified batch layers against the composite",
        lambda: _verify_batch(app, layers, per_axis, tolerance),
        prompt=(
            "Layers listed in 'no_op_layers' do not change the composite at all. "
            "Re-check their blend mode against the backdrop, or raise their opacity."
        ),
    )


def _verify_batch(
    app: Photoshop,
    layers: Optional[Sequence[str]],
    per_axis: int,
    tolerance: float,
) -> Dict[str, Any]:
    document = app.activeDocument
    if document is None:
        return {"error": "No active document"}

    if layers:
        names: List[str] = [str(name) for name in layers]
    else:
        names = [layer.name for layer in (document.layers or []) if getattr(layer, "name", None)]

    reports = [probe_layer_effect(app, name, per_axis=per_axis, tolerance=tolerance) for name in names]

    no_op_layers = [report["layer"] for report in reports if report.get("no_op") is True]
    inconclusive = [report["layer"] for report in reports if report.get("status") in _INCONCLUSIVE]
    missing = [report["layer"] for report in reports if report.get("status") == STATUS_MISSING]

    return {
        "layer_count": len(reports),
        "checked_layers": names,
        "no_op_layers": no_op_layers,
        "no_op_count": len(no_op_layers),
        "inconclusive_layers": inconclusive,
        "missing_layers": missing,
        "per_axis": per_axis,
        "samples_per_layer": per_axis**2,
        "tolerance": tolerance,
        "per_layer": reports,
        "warning": _warning(no_op_layers, inconclusive, missing),
    }


def _warning(no_op_layers: List[str], inconclusive: List[str], missing: List[str]) -> Optional[str]:
    """Build a one-line warning, or ``None`` when there is nothing to flag."""
    parts = []
    if no_op_layers:
        parts.append(f"{len(no_op_layers)} layer(s) do not change the composite: {', '.join(no_op_layers)}")
    if inconclusive:
        parts.append(f"{len(inconclusive)} layer(s) could not be sampled: {', '.join(inconclusive)}")
    if missing:
        parts.append(f"{len(missing)} layer(s) not found: {', '.join(missing)}")
    return "; ".join(parts) or None


def main(**kwargs) -> dict:
    return verify_layer_batch(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
