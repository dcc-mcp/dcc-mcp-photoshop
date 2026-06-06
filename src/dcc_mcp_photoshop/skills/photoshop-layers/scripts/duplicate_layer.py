"""Duplicate a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def duplicate_layer(name: str, new_name: str = "", **kwargs) -> dict:
    """Duplicate a named layer in the active Photoshop document.

    Args:
        name: Exact name of the source layer.
        new_name: Optional name for the duplicate; if omitted Photoshop
            appends " copy" automatically.

    Returns:
        dict: ActionResultModel with the duplicate layer id and name.
    """
    app = Photoshop()

    return action_result(
        f"Duplicated layer '{name}'",
        lambda: _duplicate_layer(app, name, new_name),
        prompt="Use rename_layer or set_layer_opacity to adjust the duplicate.",
    )


def _duplicate_layer(app: Photoshop, name: str, new_name: str) -> dict:
    descriptor = {"_obj": "duplicate", "_target": [{"_ref": "layer", "_name": name}]}
    if new_name:
        descriptor["name"] = new_name

    result = app.batch_play([descriptor], modal=True, command_name="Duplicate layer")

    if isinstance(result, list) and result:
        layer_info = result[0]
    elif isinstance(result, dict):
        layer_info = result
    else:
        layer_info = {}

    dup_name = new_name or f"{name} copy"
    return {
        "source_layer": name,
        "layer_id": layer_info.get("id"),
        "layer_name": layer_info.get("name", dup_name),
    }


def main(**kwargs) -> dict:
    return duplicate_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
