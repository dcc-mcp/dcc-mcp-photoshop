"""Get text properties from a text layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def get_text_layer_info(name: str, **kwargs) -> dict:
    """Get the text content and style properties of a text layer.

    Args:
        name: Exact name of the text layer.

    Returns:
        dict: ActionResultModel with text content, font, size, color,
            alignment, and style flags.
    """
    app = Photoshop()

    return action_result(
        f"Got text info for layer '{name}'",
        lambda: _get_text_info(app, name),
    )


def _get_text_info(app: Photoshop, name: str) -> dict:
    text_info = app.activeText

    if app.activeDocument:
        for layer in app.activeDocument.layers:
            if layer.name == name and layer.textItem:
                text_info = layer.textItem
                break

    if text_info is None:
        return {"layer_name": name, "content": None, "font": None, "size": None}

    char_style = text_info.characterStyle if text_info.characterStyle else None

    return {
        "layer_name": name,
        "content": text_info.contents,
        "font": _safe_attr(char_style, "font") if char_style else None,
        "size": _safe_attr(char_style, "size") if char_style else None,
        "color": _safe_attr(char_style, "color") if char_style else None,
        "alignment": _safe_attr(text_info, "alignment"),
        "bold": None,
        "italic": None,
    }


def _safe_attr(obj, name: str):
    try:
        return getattr(obj, name, None)
    except AttributeError:
        return None


def main(**kwargs) -> dict:
    return get_text_layer_info(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
