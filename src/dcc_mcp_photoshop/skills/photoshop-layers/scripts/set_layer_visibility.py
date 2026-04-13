"""Show or hide a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def set_layer_visibility(name: str, visible: bool, **kwargs) -> dict:
    """Show or hide a named layer.

    Args:
        name: Exact layer name.
        visible: ``True`` to show, ``False`` to hide.

    Returns:
        dict: ActionResultModel with the current visibility state.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.setLayerVisibility", name=name, visible=visible)

    state = "visible" if result.get("visible", visible) else "hidden"
    return ps_success(
        f"Layer '{name}' is now {state}",
        layer_name=name,
        visible=result.get("visible", visible),
    )


def main(**kwargs) -> dict:
    return set_layer_visibility(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
