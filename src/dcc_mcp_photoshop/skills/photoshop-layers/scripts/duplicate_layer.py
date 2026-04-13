"""Duplicate a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def duplicate_layer(name: str, new_name: str = "", **kwargs) -> dict:
    """Duplicate a named layer in the active Photoshop document.

    Args:
        name: Exact name of the source layer.
        new_name: Optional name for the duplicate; if omitted Photoshop
            appends " copy" automatically.

    Returns:
        dict: ActionResultModel with the duplicate layer id and name.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    params = {"name": name}
    if new_name:
        params["new_name"] = new_name

    result = bridge.call("ps.duplicateLayer", **params)

    return ps_success(
        f"Duplicated layer '{name}' → '{result.get('name')}'",
        prompt="Use rename_layer or set_layer_opacity to adjust the duplicate.",
        source_layer=name,
        layer_id=result.get("id"),
        layer_name=result.get("name"),
    )


def main(**kwargs) -> dict:
    return duplicate_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
