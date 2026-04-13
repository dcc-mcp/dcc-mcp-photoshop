"""Create a new layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def create_layer(
    name: str = "Layer",
    layer_type: str = "pixel",
    **kwargs,
) -> dict:
    """Create a new layer in the active Photoshop document.

    Args:
        name: Layer name (default "Layer").
        layer_type: "pixel" (default) or "group".

    Returns:
        dict: ActionResultModel with the new layer id, name, and type.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.createLayer", name=name, type=layer_type)

    return ps_success(
        f"Created {layer_type} layer '{result.get('name', name)}'",
        prompt="Use set_layer_opacity or fill_layer to style the new layer.",
        layer_id=result.get("id"),
        layer_name=result.get("name"),
        layer_type=result.get("type"),
    )


def main(**kwargs) -> dict:
    return create_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
