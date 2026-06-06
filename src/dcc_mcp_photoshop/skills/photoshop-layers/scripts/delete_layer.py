"""Delete a layer from the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def delete_layer(name: str, **kwargs) -> dict:
    """Delete a named layer from the active Photoshop document.

    Args:
        name: Exact name of the layer to delete.

    Returns:
        dict: ActionResultModel confirming deletion.
    """
    app = Photoshop()

    return action_result(
        f"Deleted layer '{name}'",
        lambda: _delete_layer(app, name),
        prompt="Use list_layers to confirm the layer has been removed.",
    )


def _delete_layer(app: Photoshop, name: str) -> dict:
    app.batch_play(
        [{"_obj": "delete", "_target": [{"_ref": "layer", "_name": name}]}],
        modal=True,
        command_name="Delete layer",
    )
    return {"deleted": True, "layer_name": name}


def main(**kwargs) -> dict:
    return delete_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
