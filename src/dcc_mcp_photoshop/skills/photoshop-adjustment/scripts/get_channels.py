"""Get channel information for the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def get_channels(**kwargs) -> dict:
    """Retrieve channel information for the active document.

    Returns the active channels (visible in the Channels panel) and
    component channels (individual color channels that make up the
    composite image).

    Returns:
        dict: ActionResultModel with active_channels and component_channels lists.
    """
    app = Photoshop()

    return action_result(
        "Retrieved channel information",
        lambda: _fetch_channels(app),
        prompt="Use add_channel or remove_channel to modify the channel list.",
    )


def _fetch_channels(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    channels = doc.channels

    active_channels = []
    component_channels = []

    for index, ch in enumerate(channels):
        kind = str(ch.kind or "unknown")
        ch_info = {
            "name": ch.name,
            "kind": kind,
            "visible": ch.visible,
            "opacity": ch.opacity,
            "index": index,
        }

        if "component" in kind.lower():
            component_channels.append(ch_info)
        else:
            active_channels.append(ch_info)

    return {
        "active_channels": active_channels,
        "component_channels": component_channels,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to get_channels."""
    return get_channels(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
