"""Set the blend mode of a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry

VALID_BLEND_MODES = [
    "normal", "dissolve",
    "darken", "multiply", "color_burn", "linear_burn", "darker_color",
    "lighten", "screen", "color_dodge", "linear_dodge", "lighter_color",
    "overlay", "soft_light", "hard_light", "vivid_light", "linear_light",
    "pin_light", "hard_mix",
    "difference", "exclusion", "subtract", "divide",
    "hue", "saturation", "color", "luminosity",
]


@skill_entry
def set_layer_blend_mode(name: str, blend_mode: str, **kwargs) -> dict:
    """Set the blend mode of a named layer.

    Args:
        name: Exact layer name.
        blend_mode: Blend mode string, e.g. ``"multiply"``, ``"screen"``,
            ``"overlay"``, ``"soft_light"``, ``"normal"``.
            Full list: normal, dissolve, darken, multiply, color_burn,
            linear_burn, darker_color, lighten, screen, color_dodge,
            linear_dodge, lighter_color, overlay, soft_light, hard_light,
            vivid_light, linear_light, pin_light, hard_mix, difference,
            exclusion, subtract, divide, hue, saturation, color, luminosity.

    Returns:
        dict: ActionResultModel confirming the blend mode change.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.setLayerBlendMode", name=name, blend_mode=blend_mode)

    return ps_success(
        f"Set blend mode of '{name}' to '{blend_mode}'",
        layer_name=name,
        blend_mode=result.get("blend_mode", blend_mode),
    )


def main(**kwargs) -> dict:
    return set_layer_blend_mode(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
