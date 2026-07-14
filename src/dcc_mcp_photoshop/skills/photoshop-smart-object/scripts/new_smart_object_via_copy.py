"""Create a new smart object by copying the active layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def new_smart_object_via_copy(**kwargs) -> dict:
    """Create a new smart object by copying the active layer.

    Returns:
        dict: ActionResultModel with the name of the new smart object.
    """
    app = Photoshop()

    return action_result(
        "Created new smart object via copy",
        lambda: _new_smart_object_via_copy(app),
        prompt="Use list_layers to confirm the new smart object layer was created.",
    )


def _new_smart_object_via_copy(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    if layer is None:
        return {"error": "No active layer"}

    so = layer.smart_object
    result = so.new_smart_object_via_copy()

    return {
        "copied": True,
        "layer_name": result.name if hasattr(result, "name") else layer.name,
    }


def main(**kwargs) -> dict:
    return new_smart_object_via_copy(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
