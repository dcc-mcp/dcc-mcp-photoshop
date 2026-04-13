"""Resize the canvas of the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def resize_canvas(
    width: int,
    height: int,
    anchor: str = "center",
    **kwargs,
) -> dict:
    """Resize the canvas without resampling the existing content.

    New pixels are filled with the background color.

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
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.resizeCanvas", width=width, height=height, anchor=anchor)

    return ps_success(
        f"Canvas resized to {result.get('width', width)}×{result.get('height', height)}px",
        width=result.get("width", width),
        height=result.get("height", height),
        anchor=anchor,
    )


def main(**kwargs) -> dict:
    return resize_canvas(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
