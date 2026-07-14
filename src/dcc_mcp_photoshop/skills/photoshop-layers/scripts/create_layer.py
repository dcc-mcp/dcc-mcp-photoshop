"""Create a new layer in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._layer_operations import rename_layer_by_id


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
    app = Photoshop()

    return action_result(
        f"Created {layer_type} layer '{name}'",
        lambda: _create_layer(app, name, layer_type),
        prompt="Use set_layer_opacity or fill_layer to style the new layer.",
    )


def _create_layer(app: Photoshop, name: str, layer_type: str) -> dict:
    if layer_type == "group":
        result = app.batch_play(
            [{"_obj": "make", "_target": [{"_ref": "layerSection"}], "name": name}],
            modal=True,
            command_name="Create group",
        )
    else:
        result = app.batch_play(
            [{"_obj": "make", "_target": [{"_ref": "layer"}], "name": name}],
            modal=True,
            command_name="Create layer",
        )

    layer = app.activeLayer
    if layer is None or layer.id is None:
        raise RuntimeError(f"Photoshop did not create the layer: {result!r}")
    rename_layer_by_id(app, layer.id, name)

    return {
        "layer_id": layer.id,
        "layer_name": name,
        "layer_type": layer_type,
    }


def main(**kwargs) -> dict:
    return create_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
