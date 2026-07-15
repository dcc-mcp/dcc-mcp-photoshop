"""Create a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._color import hex_to_rgb


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


def _create_text(
    app: Photoshop,
    content: str,
    name: str,
    x: float,
    y: float,
    font_name: str,
    font_size: float,
    hex_color: str,
    alignment: str,
    bold: bool,
    italic: bool,
) -> dict:
    document = app.activeDocument
    if document is None:
        raise RuntimeError("No active Photoshop document")
    red, green, blue = hex_to_rgb(hex_color)
    text_length = len(content)
    horizontal = 100.0 * x / float(document.width)
    vertical = 100.0 * y / float(document.height)
    descriptor = {
        "_obj": "make",
        "_target": [{"_ref": "textLayer"}],
        "using": {
            "_obj": "textLayer",
            "name": name,
            "textKey": content,
            "textClickPoint": {
                "_obj": "paint",
                "horizontal": {"_unit": "percentUnit", "_value": horizontal},
                "vertical": {"_unit": "percentUnit", "_value": vertical},
            },
            "textStyleRange": [
                {
                    "_obj": "textStyleRange",
                    "from": 0,
                    "to": text_length,
                    "textStyle": {
                        "_obj": "textStyle",
                        "fontPostScriptName": font_name,
                        "size": {"_unit": "pointsUnit", "_value": font_size},
                        "color": {"_obj": "RGBColor", "red": red, "grain": green, "blue": blue},
                        "syntheticBold": bold,
                        "syntheticItalic": italic,
                    },
                }
            ],
            "paragraphStyleRange": [
                {
                    "_obj": "paragraphStyleRange",
                    "from": 0,
                    "to": text_length,
                    "paragraphStyle": {
                        "_obj": "paragraphStyle",
                        "align": {"_enum": "alignmentType", "_value": alignment},
                    },
                }
            ],
        },
    }
    result = app.batch_play([descriptor], modal=True, command_name="Create text layer")
    if not isinstance(result, list) or not result:
        raise RuntimeError(f"Photoshop did not create the text layer: {result!r}")
    layer_id = result[0].get("layerID", result[0].get("id"))
    if layer_id is None:
        raise RuntimeError(f"Photoshop did not create the text layer: {result!r}")

    return {
        "layer_id": layer_id,
        "layer_name": name,
        "content": content,
        "font": font_name,
        "size": font_size,
        "color": hex_color,
    }


def main(**kwargs) -> dict:
    return create_text_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
