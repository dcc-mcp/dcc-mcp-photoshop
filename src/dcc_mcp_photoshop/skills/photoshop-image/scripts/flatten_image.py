"""Flatten all layers in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def flatten_image(**kwargs) -> dict:
    """Flatten all layers into a single background layer.

    WARNING: This operation is destructive — all layer data is merged
    and cannot be undone after saving.

    Returns:
        dict: ActionResultModel confirming the flatten.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.flattenImage")

    return ps_success(
        "Image flattened to a single background layer",
        prompt="Use export_document or save_document to preserve the result.",
        flattened=result.get("flattened", True),
    )


def main(**kwargs) -> dict:
    return flatten_image(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
