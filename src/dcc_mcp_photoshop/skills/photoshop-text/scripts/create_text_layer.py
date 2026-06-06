"""Create a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def create_text_layer(
    content: str,
    name: str = "",
    x: float = 100.0,
    y: float = 100.0,
    font: str = "ArialMT",
    size: float = 48.0,
    color: str = "#000000",
    alignment: str = "left",
    bold: bool = False,
    italic: bool = False,
    **kwargs,
) -> dict:
    """Create a new text layer.

    Args:
        content: The text string to display.
        name: Layer name; defaults to first 20 chars of content.
        x: Horizontal position of the text anchor in pixels (default 100).
        y: Vertical position of the text anchor in pixels (default 100).
        font: PostScript font name (default ``"ArialMT"``).
        size: Font size in points (default 48).
        color: Text color as hex string (default ``"#000000"`` — black).
        alignment: ``"left"`` (default), ``"center"``, or ``"right"``.
        bold: Bold style (default ``False``).
        italic: Italic style (default ``False``).

    Returns:
        dict: ActionResultModel with layer id, name, and text properties.
    """
    app = Photoshop()
    layer_name = name or content[:20]

    return action_result(
        f"Created text layer '{layer_name}'",
        lambda: _create_text(app, content, layer_name, x, y, font, size, color, alignment, bold, italic),
        prompt="Use update_text_layer to change the text or style later.",
    )


def _create_text(app: Photoshop, content: str, name: str, x: float, y: float, font_name: str,
                 font_size: float, hex_color: str, alignment: str, bold: bool, italic: bool) -> dict:
    r, g, b = _hex_to_rgb(hex_color)
    alignment_map = {"left": "left", "center": "center", "right": "right"}

    result = app.batch_play(
        [
            {
                "_obj": "make",
                "_target": [{"_ref": "textLayer"}],
                "using": {
                    "_obj": "textLayer",
                    "textKey": content,
                    "fontName": font_name,
                    "fontSize": {"_unit": "pointsUnit", "_value": font_size},
                    "color": {"_obj": "RGBColor", "red": r, "green": g, "blue": b},
                    "alignment": {"_enum": "alignmentType", "_value": alignment_map.get(alignment, "left")},
                    "fontCaps": {"_enum": "fontCaps", "_value": "normal"},
                    "syntheticBold": bold,
                    "syntheticItalic": italic,
                    "position": {
                        "_obj": "paint",
                        "horizontal": {"_unit": "pixelsUnit", "_value": x},
                        "vertical": {"_unit": "pixelsUnit", "_value": y},
                    },
                },
            }
        ],
        modal=True,
        command_name="Create text layer",
    )

    if isinstance(result, list) and result:
        layer_info = result[0]
    elif isinstance(result, dict):
        layer_info = result
    else:
        layer_info = {}

    return {
        "layer_id": layer_info.get("id"),
        "layer_name": layer_info.get("name", name),
        "content": content,
        "font": font_name,
        "size": font_size,
        "color": hex_color,
    }


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def main(**kwargs) -> dict:
    return create_text_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
