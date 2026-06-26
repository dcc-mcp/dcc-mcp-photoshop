"""Apply Gaussian blur filter to the active Photoshop layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def apply_gaussian_blur(
    radius: float,
    **kwargs,
) -> dict:
    """Apply Gaussian blur to the active layer.

    Args:
        radius: Blur radius in pixels.

    Returns:
        dict: ActionResultModel with filter parameters.
    """
    app = Photoshop()

    return action_result(
        f"Applied Gaussian blur (radius={radius})",
        lambda: _do_apply(app, radius),
        prompt="Increase radius for a stronger blur effect.",
    )


def _do_apply(app: Photoshop, radius: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = doc.activeLayer
    layer.filters.apply_gaussian_blur(radius)

    return {"filter": "gaussian_blur", "radius": radius}


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_gaussian_blur."""
    return apply_gaussian_blur(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
