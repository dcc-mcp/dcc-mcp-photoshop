"""Rename a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def rename_layer(name: str, new_name: str, **kwargs) -> dict:
    """Rename a layer in the active Photoshop document.

    Args:
        name: Current name of the layer.
        new_name: New name to assign.

    Returns:
        dict: ActionResultModel with old and new names.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.renameLayer", name=name, new_name=new_name)

    return ps_success(
        f"Renamed layer '{name}' → '{result.get('name', new_name)}'",
        old_name=result.get("old_name", name),
        new_name=result.get("name", new_name),
    )


def main(**kwargs) -> dict:
    return rename_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
