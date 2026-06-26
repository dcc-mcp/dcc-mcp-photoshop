"""Apply High Pass filter to the active Photoshop layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def apply_high_pass(
    radius: float,
    **kwargs,
) -> dict:
    """Apply High Pass filter to the active layer.

    Args:
        radius: Filter radius in pixels.

    Returns:
        dict: ActionResultModel with filter parameters.
    """
    app = Photoshop()

    return action_result(
        f"Applied High Pass filter (radius={radius})",
        lambda: _do_apply(app, radius),
        prompt="Lower radius preserves more detail; higher radius increases contrast.",
    )


def _do_apply(app: Photoshop, radius: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = doc.activeLayer
    layer.filters.apply_high_pass(radius)

    return {"filter": "high_pass", "radius": radius}


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_high_pass."""
    return apply_high_pass(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
