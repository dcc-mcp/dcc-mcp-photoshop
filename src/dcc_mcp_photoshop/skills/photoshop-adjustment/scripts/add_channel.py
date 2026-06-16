"""Add a new channel to the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def add_channel(
    name: str,
    **kwargs,
) -> dict:
    """Add a new alpha channel to the active document.

    Args:
        name: The name for the new channel.

    Returns:
        dict: ActionResultModel with the channel name and batchPlay result.
    """
    app = Photoshop()

    return action_result(
        f"Added channel '{name}'",
        lambda: _do_add_channel(app, name),
        prompt=f"Channel '{name}' added. Use get_channels to verify.",
    )


def _do_add_channel(app: Photoshop, name: str) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    result = app.batch_play(
        [
            {
                "_obj": "make",
                "_target": [{"_ref": "channel"}],
                "using": {"_enum": "channel", "_value": "new"},
                "name": name,
            }
        ],
        modal=True,
    )

    return {
        "channel_name": name,
        "result": result,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to add_channel."""
    return add_channel(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
