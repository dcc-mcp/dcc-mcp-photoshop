"""Resize the canvas of the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def resize_canvas(
    width: int,
    height: int,
    anchor: str = "center",
    **kwargs,
) -> dict:
    """Resize the canvas without resampling the existing content.

    Args:
        width: New canvas width in pixels.
        height: New canvas height in pixels.
        anchor: Where to position the existing content within the new canvas.
            One of: ``"top_left"``, ``"top_center"``, ``"top_right"``,
            ``"middle_left"``, ``"center"`` (default), ``"middle_right"``,
            ``"bottom_left"``, ``"bottom_center"``, ``"bottom_right"``.

    Returns:
        dict: ActionResultModel with new dimensions.
    """
    app = Photoshop()

    return action_result(
        f"Canvas resized to {width}×{height}px",
        lambda: _resize_canvas(app, width, height, anchor),
    )


def _resize_canvas(app: Photoshop, width: int, height: int, anchor: str) -> dict:
    app.batch_play(
        [
            {
                "_obj": "canvasSize",
                "width": {"_unit": "pixelsUnit", "_value": width},
                "height": {"_unit": "pixelsUnit", "_value": height},
                "horizontal": {"_enum": "horizontalLocation", "_value": _anchor_horizontal(anchor)},
                "vertical": {"_enum": "verticalLocation", "_value": _anchor_vertical(anchor)},
            }
        ],
        modal=True,
        command_name="Resize canvas",
    )
    return {"width": width, "height": height, "anchor": anchor}


def _anchor_horizontal(anchor: str) -> str:
    if "left" in anchor:
        return "left"
    if "right" in anchor:
        return "right"
    return "center"


def _anchor_vertical(anchor: str) -> str:
    if "top" in anchor:
        return "top"
    if "bottom" in anchor:
        return "bottom"
    return "middle"


def main(**kwargs) -> dict:
    return resize_canvas(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
