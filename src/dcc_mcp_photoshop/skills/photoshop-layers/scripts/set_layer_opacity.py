"""Set layer opacity in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def set_layer_opacity(name: str, opacity: float, **kwargs) -> dict:
    """Set the opacity of a named layer (0–100).

    Args:
        name: Exact layer name.
        opacity: Opacity value 0 (transparent) to 100 (opaque).

    Returns:
        dict: ActionResultModel with the applied opacity.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.setLayerOpacity", name=name, opacity=opacity)

    return ps_success(
        f"Set opacity of '{name}' to {result.get('opacity', opacity)}%",
        layer_name=name,
        opacity=result.get("opacity", opacity),
    )


def main(**kwargs) -> dict:
    return set_layer_opacity(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
