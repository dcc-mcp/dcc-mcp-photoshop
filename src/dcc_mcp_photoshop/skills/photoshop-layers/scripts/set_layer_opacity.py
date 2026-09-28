"""Set layer opacity in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._layer_effect import (
    DEFAULT_PER_AXIS,
    DEFAULT_TOLERANCE,
    probe_layer_effect,
)


@skill_entry
def set_layer_opacity(
    name: str,
    opacity: float,
    verify: bool = True,
    per_axis: int = DEFAULT_PER_AXIS,
    tolerance: float = DEFAULT_TOLERANCE,
    **kwargs,
) -> dict:
    """Set the opacity of a named layer (0–100).

    Opacity is not the only thing that decides whether a layer is visible: at
    ``0%`` it contributes nothing, and so does any opacity when the blend mode
    is a no-op over the backdrop. With ``verify`` enabled (the default) the
    call measures the layer's real composite contribution and reports
    ``effect.no_op``.

    Args:
        name: Exact layer name.
        opacity: Opacity value 0 (transparent) to 100 (opaque).
        verify: Measure the composite effect after the change. Set to ``False``
            to skip the read-back and keep the call cheap.
        per_axis: Sample points per axis used by the verification probe.
        tolerance: Largest per-channel delta (0-255) still counted as invisible.

    Returns:
        dict: ActionResultModel with the applied opacity and an ``effect``
        block describing the measured composite contribution.
    """
    app = Photoshop()

    return action_result(
        f"Set opacity of '{name}' to {opacity}%",
        lambda: _set_opacity(app, name, opacity, verify, per_axis, tolerance),
        prompt=(
            "If 'effect.no_op' is true the layer is invisible in the composite "
            "at this opacity — check the blend mode against the backdrop too."
        ),
    )


def _set_opacity(
    app: Photoshop,
    name: str,
    opacity: float,
    verify: bool = True,
    per_axis: int = DEFAULT_PER_AXIS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict:
    app.batch_play(
        [
            {
                "_obj": "set",
                "_target": [{"_ref": "layer", "_name": name}],
                "to": {"_obj": "layer", "opacity": {"_unit": "percentUnit", "_value": opacity}},
            }
        ],
        modal=True,
        command_name="Set layer opacity",
    )
    payload = {"layer_name": name, "opacity": opacity}
    if verify:
        effect = probe_layer_effect(app, name, per_axis=per_axis, tolerance=tolerance)
        payload["effect"] = effect
        payload["no_op"] = effect["no_op"]
        payload["warning"] = effect.get("reason") if effect["no_op"] else None
    return payload


def main(**kwargs) -> dict:
    return set_layer_opacity(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
