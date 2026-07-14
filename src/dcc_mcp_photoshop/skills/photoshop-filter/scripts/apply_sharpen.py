"""Apply Sharpen filter to the active Photoshop layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def apply_sharpen(**kwargs) -> dict:
    """Apply Sharpen filter to the active layer.

    Returns:
        dict: ActionResultModel confirming the filter was applied.
    """
    app = Photoshop()

    return action_result(
        "Applied Sharpen filter",
        lambda: _do_apply(app),
        prompt="Sharpen enhances edge contrast. Use High Pass for more control.",
    )


def _do_apply(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    layer.filters.apply_sharpen()

    return {"filter": "sharpen"}


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_sharpen."""
    return apply_sharpen(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
