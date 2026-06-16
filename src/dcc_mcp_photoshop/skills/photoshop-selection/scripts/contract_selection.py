"""Contract the current selection by a given number of pixels."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def contract_selection(by: float, **kwargs) -> dict:
    """Shrink the current selection inward by the specified pixel amount.

    Args:
        by: Number of pixels to contract the selection.

    Returns:
        dict: ActionResultModel with the contracted selection bounds.
    """
    app = Photoshop()

    return action_result(
        f"Contracted selection by {by}px",
        lambda: _do_contract_selection(app, by),
        prompt="Use expand_selection to grow, or feather_selection to soften edges.",
    )


def _do_contract_selection(app: Photoshop, by: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.contract(by)
    bounds = doc.selection.bounds

    return {"bounds": bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to contract_selection."""
    return contract_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
