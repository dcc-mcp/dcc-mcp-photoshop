"""Fill a layer with a solid color in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def fill_layer(
    name: str,
    color: str = "#ffffff",
    opacity: float = 100.0,
    **kwargs,
) -> dict:
    """Fill a layer with a solid color.

    Args:
        name: Exact layer name.
        color: Fill color as a hex string (e.g. ``"#ff0000"`` for red) or
            ``"transparent"`` to clear.  Default is white ``"#ffffff"``.
        opacity: Fill opacity 0-100 (default 100).

    Returns:
        dict: ActionResultModel confirming the fill.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.fillLayer", name=name, color=color, opacity=opacity)

    return ps_success(
        f"Filled layer '{name}' with {color}",
        layer_name=name,
        color=color,
        opacity=opacity,
        filled=result.get("filled", True),
    )


def main(**kwargs) -> dict:
    return fill_layer(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
