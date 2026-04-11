"""Get information about the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry, skill_success


@skill_entry
def get_document_info(**kwargs) -> dict:
    """Get metadata about the currently active Photoshop document.

    Returns:
        dict: ActionResultModel with document name, dimensions, color mode, etc.
    """
    from dcc_mcp_photoshop.api import get_bridge  # noqa: PLC0415

    bridge = get_bridge()
    info = bridge.call("ps.getDocumentInfo")

    return skill_success(
        f"Retrieved document info: {info.get('name', 'Untitled')}",
        prompt="Use list_layers to inspect layers or export_document to save the document.",
        document_name=info.get("name"),
        width=info.get("width"),
        height=info.get("height"),
        resolution=info.get("resolution"),
        color_mode=info.get("colorMode"),
        bit_depth=info.get("bitsPerChannel"),
    )


def main(**kwargs) -> dict:
    """Entry point; delegates to get_document_info."""
    return get_document_info(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
