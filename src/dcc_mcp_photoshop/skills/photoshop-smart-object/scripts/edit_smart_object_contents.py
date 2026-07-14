"""Edit the contents of the active smart object layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def edit_smart_object_contents(**kwargs) -> dict:
    """Open the active smart object for content editing.

    Returns:
        dict: ActionResultModel confirming the smart object is open for editing.
    """
    app = Photoshop()

    return action_result(
        "Opened smart object for editing",
        lambda: _edit_smart_object_contents(app),
        prompt="The smart object is now open in a separate document. Make your edits and save to update the smart object.",
    )


def _edit_smart_object_contents(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    if layer is None:
        return {"error": "No active layer"}

    so = layer.smart_object
    so.edit_contents()

    return {
        "editing": True,
        "layer_name": layer.name,
    }


def main(**kwargs) -> dict:
    return edit_smart_object_contents(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
