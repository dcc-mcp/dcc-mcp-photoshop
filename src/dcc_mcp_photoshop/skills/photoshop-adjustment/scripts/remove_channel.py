"""Remove a channel from the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def remove_channel(
    name: str,
    **kwargs,
) -> dict:
    """Remove a channel by name from the active document.

    Args:
        name: The name of the channel to remove.

    Returns:
        dict: ActionResultModel with the removed channel name and batchPlay result.
    """
    app = Photoshop()

    return action_result(
        f"Removed channel '{name}'",
        lambda: _do_remove_channel(app, name),
        prompt=f"Channel '{name}' removed. Use get_channels to verify.",
    )


def _do_remove_channel(app: Photoshop, name: str) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    result = app.batch_play(
        [
            {
                "_obj": "delete",
                "_target": [{"_ref": "channel", "_name": name}],
            }
        ],
        modal=True,
    )

    return {
        "channel_name": name,
        "result": result,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to remove_channel."""
    return remove_channel(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
