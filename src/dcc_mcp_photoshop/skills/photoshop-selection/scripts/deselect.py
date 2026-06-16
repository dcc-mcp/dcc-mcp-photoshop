"""Clear the current selection in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def deselect(**kwargs) -> dict:
    """Remove the current selection (deselect all).

    Returns:
        dict: ActionResultModel confirming the selection was cleared.
    """
    app = Photoshop()

    return action_result(
        "Deselected",
        lambda: _do_deselect(app),
        prompt="Use select_all or select_rectangle to create a new selection.",
    )


def _do_deselect(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.deselect()

    return {"deselected": True}


def main(**kwargs) -> dict:
    """Entry point; delegates to deselect."""
    return deselect(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
