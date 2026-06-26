"""Expand the current selection by a given number of pixels."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def expand_selection(by: float, **kwargs) -> dict:
    """Expand the current selection outward by the specified pixel amount.

    Args:
        by: Number of pixels to expand the selection.

    Returns:
        dict: ActionResultModel with the expanded selection bounds.
    """
    app = Photoshop()

    return action_result(
        f"Expanded selection by {by}px",
        lambda: _do_expand_selection(app, by),
        prompt="Use contract_selection to shrink, or feather_selection to soften edges.",
    )


def _do_expand_selection(app: Photoshop, by: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.expand(by)
    bounds = doc.selection.bounds

    return {"bounds": bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to expand_selection."""
    return expand_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
