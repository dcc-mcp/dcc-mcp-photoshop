"""Get text properties from a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def get_text_layer_info(name: str, **kwargs) -> dict:
    """Get the text content and style properties of a text layer.

    Args:
        name: Exact name of the text layer.

    Returns:
        dict: ActionResultModel with text content, font, size, color,
            alignment, and style flags.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.getTextLayerInfo", name=name)

    return ps_success(
        f"Got text info for layer '{name}'",
        layer_name=name,
        content=result.get("content"),
        font=result.get("font"),
        size=result.get("size"),
        color=result.get("color"),
        alignment=result.get("alignment"),
        bold=result.get("bold"),
        italic=result.get("italic"),
    )


def main(**kwargs) -> dict:
    return get_text_layer_info(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
