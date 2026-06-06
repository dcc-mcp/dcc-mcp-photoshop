"""Get information about the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def get_document_info(**kwargs) -> dict:
    """Get metadata about the currently active Photoshop document.

    Returns:
        dict: ActionResultModel with document name, dimensions, color mode, etc.
    """
    app = Photoshop()

    return action_result(
        "Retrieved document info",
        lambda: _fetch_document_info(app),
        prompt="Use list_layers to inspect layers or export_document to save the document.",
    )


def _fetch_document_info(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"document_name": None, "error": "No active document"}

    return {
        "document_name": doc.name,
        "width": doc.width,
        "height": doc.height,
        "resolution": doc.resolution,
        "color_mode": doc.mode,
        "bit_depth": None,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to get_document_info."""
    return get_document_info(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
