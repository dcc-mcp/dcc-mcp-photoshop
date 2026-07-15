"""Create a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._color import solid_color_payload
from dcc_mcp_photoshop._layer_operations import rename_layer_by_id


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
    result = app.dom.app.activeDocument.createTextLayer(
        {
            "name": name,
            "contents": content,
            "fontName": font_name,
            "fontSize": font_size,
            "position": {"x": x, "y": y},
        },
        modal=True,
        command_name="Create text layer",
    )
    if not isinstance(result, dict) or result.get("id") is None:
        raise RuntimeError(f"Photoshop did not create the text layer: {result!r}")

    rename_layer_by_id(app, result["id"], name)
    text_item = app.activeLayer.text_item
    text_item.set_character_style(
        {
            "font": font_name,
            "size": font_size,
            "fauxBold": bold,
            "fauxItalic": italic,
            "color": solid_color_payload(hex_color),
        },
        command_name="Style text layer",
    )
    text_item.set_paragraph_style(
        {"justification": alignment if alignment in {"left", "center", "right"} else "left"},
        command_name="Align text layer",
    )

    return {
        "layer_id": result["id"],
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
