"""Create an elliptical selection in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def select_ellipse(
    top: float,
    left: float,
    bottom: float,
    right: float,
    **kwargs,
) -> dict:
    """Create an elliptical selection bounded by the given pixel coordinates.

    Args:
        top: Top edge in pixels.
        left: Left edge in pixels.
        bottom: Bottom edge in pixels.
        right: Right edge in pixels.

    Returns:
        dict: ActionResultModel with the new selection bounds.
    """
    app = Photoshop()

    return action_result(
        f"Created elliptical selection ({left}, {top}) to ({right}, {bottom})",
        lambda: _do_select_ellipse(app, top, left, bottom, right),
        prompt="Use inverse_selection to invert, or feather_selection to soften edges.",
    )


def _do_select_ellipse(
    app: Photoshop,
    top: float,
    left: float,
    bottom: float,
    right: float,
) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    bounds = {"top": top, "left": left, "bottom": bottom, "right": right}
    doc.selection.select_ellipse(bounds)
    result_bounds = doc.selection.bounds

    return {"bounds": result_bounds}


def main(**kwargs) -> dict:
    """Entry point; delegates to select_ellipse."""
    return select_ellipse(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
