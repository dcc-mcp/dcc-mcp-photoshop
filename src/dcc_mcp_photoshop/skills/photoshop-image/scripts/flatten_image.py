"""Flatten all layers in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def flatten_image(**kwargs) -> dict:
    """Flatten all layers into a single background layer.

    WARNING: This operation is destructive — all layer data is merged
    and cannot be undone after saving.

    Returns:
        dict: ActionResultModel confirming the flatten.
    """
    app = Photoshop()

    return action_result(
        "Image flattened to a single background layer",
        lambda: _flatten(app),
        prompt="Use export_document or save_document to preserve the result.",
    )


def _flatten(app: Photoshop) -> dict:
    app.batch_play(
        [{"_obj": "flattenImage"}],
        modal=True,
        command_name="Flatten image",
    )
    return {"flattened": True}


def main(**kwargs) -> dict:
    return flatten_image(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
