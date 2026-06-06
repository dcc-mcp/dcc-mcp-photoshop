"""Rename a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def rename_layer(name: str, new_name: str, **kwargs) -> dict:
    """Rename a layer in the active Photoshop document.

    Args:
        name: Current name of the layer.
        new_name: New name to assign.

    Returns:
        dict: ActionResultModel with old and new names.
    """
    app = Photoshop()

    return action_result(
        f"Renamed layer '{name}' → '{new_name}'",
        lambda: _rename_layer(app, name, new_name),
    )


def _rename_layer(app: Photoshop, name: str, new_name: str) -> dict:
    app.batch_play(
        [{"_obj": "set", "_target": [{"_ref": "layer", "_name": name}], "to": {"_obj": "layer", "name": new_name}}],
        modal=True,
        command_name="Rename layer",
    )
    return {"old_name": name, "new_name": new_name}


def main(**kwargs) -> dict:
    return rename_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
