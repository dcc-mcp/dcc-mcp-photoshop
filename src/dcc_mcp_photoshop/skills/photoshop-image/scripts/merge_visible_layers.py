"""Merge all visible layers in the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def merge_visible_layers(**kwargs) -> dict:
    """Merge all currently visible layers into one.

    Hidden layers are preserved.  Unlike ``flatten_image``, transparency
    is maintained and hidden layers are kept intact.

    Returns:
        dict: ActionResultModel confirming the merge.
    """
    app = Photoshop()

    return action_result(
        "Visible layers merged",
        lambda: _merge_visible(app),
    )


def _merge_visible(app: Photoshop) -> dict:
    app.batch_play(
        [{"_obj": "mergeVisibleLayers"}],
        modal=True,
        command_name="Merge visible layers",
    )
    return {"merged": True, "layer_name": "Merged"}


def main(**kwargs) -> dict:
    return merge_visible_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
