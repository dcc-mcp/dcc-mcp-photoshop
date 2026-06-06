"""Scale (resample) the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


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
    app = Photoshop()

    return action_result(
        f"Image resized to {width}×{height}px",
        lambda: _resize_image(app, width, height, resample, constrain_proportions),
    )


def _resize_image(app: Photoshop, width: int, height: int, resample: str, constrain_proportions: bool) -> dict:
    resample_map = {
        "bicubic": "bicubic",
        "bilinear": "bilinear",
        "nearest": "nearestNeighbor",
        "preserve_details": "bicubicAutomatic",
        "bicubic_smoother": "bicubicSmoother",
        "bicubic_sharper": "bicubicSharper",
    }

    app.batch_play(
        [
            {
                "_obj": "imageSize",
                "width": {"_unit": "pixelsUnit", "_value": width},
                "height": {"_unit": "pixelsUnit", "_value": height},
                "constrainProportions": constrain_proportions,
                "interpolationType": {
                    "_enum": "interpolationType",
                    "_value": resample_map.get(resample, "bicubic"),
                },
            }
        ],
        modal=True,
        command_name="Resize image",
    )
    return {"width": width, "height": height, "resample": resample}


def main(**kwargs) -> dict:
    return resize_image(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
