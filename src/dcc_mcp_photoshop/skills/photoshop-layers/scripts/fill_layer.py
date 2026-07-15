"""Fill a layer with a solid color in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._color import hex_to_rgb


@skill_entry
def fill_layer(
    name: str,
    color: str = "#ffffff",
    opacity: float = 100.0,
    **kwargs,
) -> dict:
    """Fill a layer with a solid color.

    Args:
        name: Exact layer name.
        color: Fill color as a hex string (e.g. ``"#ff0000"`` for red) or
            ``"transparent"`` to clear.  Default is white ``"#ffffff"``.
        opacity: Fill opacity 0-100 (default 100).

    Returns:
        dict: ActionResultModel confirming the fill.
    """
    app = Photoshop()

    return action_result(
        f"Filled layer '{name}' with {color}",
        lambda: _fill_layer(app, name, color, opacity),
    )


def _fill_layer(app: Photoshop, name: str, color: str, opacity: float) -> dict:
    if color.lower() == "transparent":
        raise ValueError("Transparent clearing is not supported by fill_layer; use a selection clear operation instead")

    red, green, blue = hex_to_rgb(color)
    app.batch_play(
        [
            {
                "_obj": "select",
                "_target": [{"_ref": "layer", "_name": name}],
                "makeVisible": False,
            },
            {
                "_obj": "fill",
                "using": {"_enum": "fillContents", "_value": "color"},
                "color": {
                    "_obj": "RGBColor",
                    "red": red,
                    "grain": green,
                    "blue": blue,
                },
                "opacity": {"_unit": "percentUnit", "_value": opacity},
                "mode": {"_enum": "blendMode", "_value": "normal"},
            },
        ],
        modal=True,
        command_name="Fill layer",
    )
    return {
        "layer_name": name,
        "color": color,
        "opacity": opacity,
        "filled": True,
    }


def main(**kwargs) -> dict:
    return fill_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
