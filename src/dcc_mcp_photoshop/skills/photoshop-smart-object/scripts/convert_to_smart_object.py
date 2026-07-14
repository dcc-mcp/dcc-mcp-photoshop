"""Convert the active layer to a smart object."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def convert_to_smart_object(**kwargs) -> dict:
    """Convert the active layer into a smart object.

    Returns:
        dict: ActionResultModel with the name of the converted smart object.
    """
    app = Photoshop()

    return action_result(
        "Converted layer to smart object",
        lambda: _convert_to_smart_object(app),
        prompt="Use list_layers to confirm the layer is now a smart object.",
    )


def _convert_to_smart_object(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    if layer is None:
        return {"error": "No active layer"}

    so = layer.smart_object
    result = so.convert_to_smart_object()

    return {
        "converted": True,
        "layer_name": result.name if hasattr(result, "name") else layer.name,
    }


def main(**kwargs) -> dict:
    return convert_to_smart_object(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
