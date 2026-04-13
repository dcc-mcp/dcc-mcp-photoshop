"""Delete a layer from the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def delete_layer(name: str, **kwargs) -> dict:
    """Delete a named layer from the active Photoshop document.

    Args:
        name: Exact name of the layer to delete.

    Returns:
        dict: ActionResultModel confirming deletion.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.deleteLayer", name=name)

    return ps_success(
        f"Deleted layer '{name}'",
        prompt="Use list_layers to confirm the layer has been removed.",
        deleted=result.get("deleted", True),
        layer_name=name,
    )


def main(**kwargs) -> dict:
    return delete_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
