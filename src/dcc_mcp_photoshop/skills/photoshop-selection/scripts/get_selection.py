"""Get the bounds of the current selection in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def get_selection(**kwargs) -> dict:
    """Retrieve the bounding box of the current selection.

    Returns:
        dict: ActionResultModel with selection bounds (top, left, bottom, right)
              or None if no selection exists.
    """
    app = Photoshop()

    return action_result(
        "Retrieved selection bounds",
        lambda: _fetch_selection(app),
        prompt="Use select_rectangle or select_ellipse to create a selection.",
    )


def _fetch_selection(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    bounds = doc.selection.bounds
    if bounds is None:
        return {"bounds": None, "has_selection": False}

    return {"bounds": bounds, "has_selection": True}


def main(**kwargs) -> dict:
    """Entry point; delegates to get_selection."""
    return get_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
