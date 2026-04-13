"""Create a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


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
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call(
        "ps.createTextLayer",
        content=content,
        name=name or content[:20],
        x=x,
        y=y,
        font=font,
        size=size,
        color=color,
        alignment=alignment,
        bold=bold,
        italic=italic,
    )

    return ps_success(
        f"Created text layer '{result.get('name', name or content[:20])}'",
        prompt="Use update_text_layer to change the text or style later.",
        layer_id=result.get("id"),
        layer_name=result.get("name"),
        content=content,
        font=font,
        size=size,
        color=color,
    )


def main(**kwargs) -> dict:
    return create_text_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
