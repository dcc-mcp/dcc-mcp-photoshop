"""Select all pixels in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def select_all(**kwargs) -> dict:
    """Select the entire canvas of the active document.

    Returns:
        dict: ActionResultModel with updated selection bounds.
    """
    app = Photoshop()

    return action_result(
        "Selected entire canvas",
        lambda: _do_select_all(app),
        prompt="Use deselect to clear the selection, or inverse_selection to invert it.",
    )


def _do_select_all(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.select_all()
    bounds = doc.selection.bounds

    return {"bounds": bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to select_all."""
    return select_all(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
