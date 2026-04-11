"""List all layers in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry, skill_success


@skill_entry
def list_layers(include_hidden: bool = True, **kwargs) -> dict:
    """List all layers in the currently active Photoshop document.

    Args:
        include_hidden: Whether to include hidden layers (default: True).

    Returns:
        dict: ActionResultModel with layer names, types, and visibility.
    """
    from dcc_mcp_photoshop.api import get_bridge  # noqa: PLC0415

    bridge = get_bridge()
    layers = bridge.call("ps.listLayers", include_hidden=include_hidden)

    layer_names = [layer.get("name", "Unnamed") for layer in layers]

    return skill_success(
        f"Found {len(layers)} layer(s) in the active document",
        prompt="Use create_layer to add a new layer or get_document_info for document metadata.",
        count=len(layers),
        layers=layer_names,
        include_hidden=include_hidden,
    )


def main(**kwargs) -> dict:
    """Entry point; delegates to list_layers."""
    return list_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
