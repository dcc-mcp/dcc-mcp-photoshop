"""Apply Smart Blur filter to the active Photoshop layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def apply_smart_blur(
    radius: float,
    threshold: float = 0.0,
    **kwargs,
) -> dict:
    """Apply Smart Blur filter to the active layer.

    Smart Blur preserves edges while smoothing areas below the threshold.

    Args:
        radius: Blur radius in pixels.
        threshold: Edge threshold. Areas with tonal difference below this
            value are blurred; areas above it are preserved. Default 0.0.

    Returns:
        dict: ActionResultModel with filter parameters.
    """
    app = Photoshop()

    return action_result(
        f"Applied Smart Blur (radius={radius}, threshold={threshold})",
        lambda: _do_apply(app, radius, threshold),
        prompt="Increase threshold to preserve more edges.",
    )


def _do_apply(app: Photoshop, radius: float, threshold: float) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    layer.filters.apply_smart_blur(radius, threshold)

    return {"filter": "smart_blur", "radius": radius, "threshold": threshold}


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_smart_blur."""
    return apply_smart_blur(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
