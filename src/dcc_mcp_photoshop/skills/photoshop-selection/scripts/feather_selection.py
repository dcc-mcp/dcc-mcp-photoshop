"""Feather the current selection by a given number of pixels."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def feather_selection(by: float, **kwargs) -> dict:
    """Soften the edges of the current selection by the specified pixel radius.

    Args:
        by: Feather radius in pixels.

    Returns:
        dict: ActionResultModel with the feathered selection bounds.
    """
    app = Photoshop()

    return action_result(
        f"Feathered selection by {by}px",
        lambda: _do_feather_selection(app, by),
        prompt="Use expand_selection or contract_selection to adjust the selection area.",
    )


def _do_feather_selection(app: Photoshop, by: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.feather(by)
    bounds = doc.selection.bounds

    return {"bounds": bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to feather_selection."""
    return feather_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
