"""Scale (resample) the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def resize_image(
    width: int,
    height: int,
    resample: str = "bicubic",
    constrain_proportions: bool = True,
    **kwargs,
) -> dict:
    """Scale the active Photoshop document (resamples content).

    Args:
        width: Target width in pixels.
        height: Target height in pixels.
        resample: Resampling algorithm — ``"bicubic"`` (default),
            ``"bilinear"``, ``"nearest"``, ``"preserve_details"``,
            ``"bicubic_smoother"``, ``"bicubic_sharper"``.
        constrain_proportions: If ``True`` (default), lock aspect ratio and
            use ``width`` as the controlling dimension.

    Returns:
        dict: ActionResultModel with new dimensions.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call(
        "ps.resizeImage",
        width=width,
        height=height,
        resample=resample,
        constrain_proportions=constrain_proportions,
    )

    return ps_success(
        f"Image resized to {result.get('width', width)}×{result.get('height', height)}px",
        width=result.get("width", width),
        height=result.get("height", height),
        resample=resample,
    )


def main(**kwargs) -> dict:
    return resize_image(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
