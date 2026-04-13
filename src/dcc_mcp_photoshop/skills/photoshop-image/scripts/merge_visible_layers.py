"""Merge all visible layers in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def merge_visible_layers(**kwargs) -> dict:
    """Merge all currently visible layers into one.

    Hidden layers are preserved.  Unlike ``flatten_image``, transparency
    is maintained and hidden layers are kept intact.

    Returns:
        dict: ActionResultModel confirming the merge.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.mergeVisibleLayers")

    return ps_success(
        "Visible layers merged",
        merged=result.get("merged", True),
        layer_name=result.get("layer_name"),
    )


def main(**kwargs) -> dict:
    return merge_visible_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
