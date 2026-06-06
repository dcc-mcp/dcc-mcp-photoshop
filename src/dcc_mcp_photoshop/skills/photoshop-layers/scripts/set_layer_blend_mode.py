"""Set the blend mode of a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

VALID_BLEND_MODES = [
    "normal", "dissolve", "darken", "multiply", "color_burn",
    "linear_burn", "darker_color", "lighten", "screen", "color_dodge",
    "linear_dodge", "lighter_color", "overlay", "soft_light", "hard_light",
    "vivid_light", "linear_light", "pin_light", "hard_mix", "difference",
    "exclusion", "subtract", "divide", "hue", "saturation", "color", "luminosity",
]


@skill_entry
def set_layer_blend_mode(name: str, blend_mode: str, **kwargs) -> dict:
    """Set the blend mode of a named layer.

    Args:
        name: Exact layer name.
        blend_mode: Blend mode string, e.g. ``"multiply"``, ``"screen"``,
            ``"overlay"``, ``"soft_light"``, ``"normal"``.

    Returns:
        dict: ActionResultModel confirming the blend mode change.
    """
    app = Photoshop()

    return action_result(
        f"Set blend mode of '{name}' to '{blend_mode}'",
        lambda: _set_blend_mode(app, name, blend_mode),
    )


def _set_blend_mode(app: Photoshop, name: str, blend_mode: str) -> dict:
    app.batch_play(
        [
            {
                "_obj": "set",
                "_target": [{"_ref": "layer", "_name": name}],
                "to": {"_obj": "layer", "mode": {"_enum": "blendMode", "_value": blend_mode}},
            }
        ],
        modal=True,
        command_name="Set layer blend mode",
    )
    return {"layer_name": name, "blend_mode": blend_mode}


def main(**kwargs) -> dict:
    return set_layer_blend_mode(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
