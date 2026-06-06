"""Set layer opacity in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def set_layer_opacity(name: str, opacity: float, **kwargs) -> dict:
    """Set the opacity of a named layer (0–100).

    Args:
        name: Exact layer name.
        opacity: Opacity value 0 (transparent) to 100 (opaque).

    Returns:
        dict: ActionResultModel with the applied opacity.
    """
    app = Photoshop()

    return action_result(
        f"Set opacity of '{name}' to {opacity}%",
        lambda: _set_opacity(app, name, opacity),
    )


def _set_opacity(app: Photoshop, name: str, opacity: float) -> dict:
    app.batch_play(
        [
            {
                "_obj": "set",
                "_target": [{"_ref": "layer", "_name": name}],
                "to": {"_obj": "layer", "opacity": {"_unit": "percentUnit", "_value": opacity}},
            }
        ],
        modal=True,
        command_name="Set layer opacity",
    )
    return {"layer_name": name, "opacity": opacity}


def main(**kwargs) -> dict:
    return set_layer_opacity(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
