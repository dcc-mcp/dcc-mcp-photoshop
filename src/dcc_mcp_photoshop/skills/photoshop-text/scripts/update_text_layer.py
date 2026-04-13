"""Update a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from typing import Optional

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
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    params = {"name": name}
    if content is not None:
        params["content"] = content
    if font is not None:
        params["font"] = font
    if size is not None:
        params["size"] = size
    if color is not None:
        params["color"] = color
    if alignment is not None:
        params["alignment"] = alignment
    if bold is not None:
        params["bold"] = bold
    if italic is not None:
        params["italic"] = italic

    result = bridge.call("ps.updateTextLayer", **params)

    return ps_success(
        f"Updated text layer '{name}'",
        layer_name=name,
        updated_fields=list(params.keys()),
        content=result.get("content"),
    )


def main(**kwargs) -> dict:
    return update_text_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
