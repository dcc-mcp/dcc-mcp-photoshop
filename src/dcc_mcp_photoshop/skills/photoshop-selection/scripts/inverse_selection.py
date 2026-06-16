"""Invert the current selection in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def inverse_selection(**kwargs) -> dict:
    """Invert the current selection so selected areas become unselected and vice versa.

    Returns:
        dict: ActionResultModel with the inverted selection bounds.
    """
    app = Photoshop()

    return action_result(
        "Inverted selection",
        lambda: _do_inverse_selection(app),
        prompt="Use select_all to reselect the entire canvas, or feather_selection to soften edges.",
    )


def _do_inverse_selection(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.inverse()
    bounds = doc.selection.bounds

    return {"bounds": bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to inverse_selection."""
    return inverse_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
