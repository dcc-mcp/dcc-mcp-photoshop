"""List all layers in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def list_layers(include_hidden: bool = True, **kwargs) -> dict:
    """List all layers in the currently active Photoshop document.

    Args:
        include_hidden: Whether to include hidden layers (default: True).

    Returns:
        dict: ActionResultModel with layer names, types, and visibility.
    """
    app = Photoshop()

    return action_result(
        "Listed layers in active document",
        lambda: _list_layers(app, include_hidden),
        prompt="Use create_layer to add a new layer or get_document_info for document metadata.",
    )


def _list_layers(app: Photoshop, include_hidden: bool) -> dict:
    layers = []
    if app.activeDocument:
        layers = app.activeDocument.layers

    if not include_hidden:
        layers = [lyr for lyr in layers if lyr.visible]

    layer_names = [lyr.name or "Unnamed" for lyr in layers]
    return {
        "count": len(layers),
        "layers": layer_names,
        "include_hidden": include_hidden,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to list_layers."""
    return list_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
