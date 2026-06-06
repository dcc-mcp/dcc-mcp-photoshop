"""Update a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from typing import Optional

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def update_text_layer(
    name: str,
    content: Optional[str] = None,
    font: Optional[str] = None,
    size: Optional[float] = None,
    color: Optional[str] = None,
    alignment: Optional[str] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    **kwargs,
) -> dict:
    """Update the content or style of an existing text layer.

    Only the provided parameters are changed; omitted ones keep their
    current values.

    Args:
        name: Exact name of the text layer to update.
        content: New text string (optional).
        font: New PostScript font name (optional).
        size: New font size in points (optional).
        color: New text color as hex string (optional).
        alignment: New alignment — ``"left"``, ``"center"``, ``"right"`` (optional).
        bold: Bold style override (optional).
        italic: Italic style override (optional).

    Returns:
        dict: ActionResultModel confirming the update.
    """
    app = Photoshop()

    updated_fields = []
    for key, val in [
        ("name", name),
        ("content", content),
        ("font", font),
        ("size", size),
        ("color", color),
        ("alignment", alignment),
        ("bold", bold),
        ("italic", italic),
    ]:
        if val is not None:
            updated_fields.append(key)

    return action_result(
        f"Updated text layer '{name}'",
        lambda: _update_text(app, name, content, font, size, color, alignment, bold, italic, updated_fields),
    )


def _update_text(
    app: Photoshop, name: str, content, font, size, color, alignment, bold, italic, updated_fields
) -> dict:
    text_item = None
    if app.activeDocument:
        for layer in app.activeDocument.layers:
            if layer.name == name and layer.textItem:
                text_item = layer.textItem
                break

    if text_item is None:
        raise ValueError(
            f"Text layer '{name}' not found or is not a text layer. "
            "Ensure the layer exists and was created as a text layer."
        )

    if content is not None:
        text_item.set_contents(content, command_name="Set text content")

    char_style_props = {}
    if font is not None:
        char_style_props["font"] = font
    if size is not None:
        char_style_props["size"] = size
    if color is not None:
        char_style_props["color"] = color
    if bold is not None:
        char_style_props["bold"] = bold
    if italic is not None:
        char_style_props["italic"] = italic

    if char_style_props:
        text_item.set_character_style(char_style_props, command_name="Set character style")

    if alignment is not None:
        text_item.set_paragraph_style({"alignment": alignment}, command_name="Set paragraph style")

    text_item.refresh()
    return {
        "layer_name": name,
        "updated_fields": updated_fields,
        "content": text_item.contents,
    }


def main(**kwargs) -> dict:
    return update_text_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
