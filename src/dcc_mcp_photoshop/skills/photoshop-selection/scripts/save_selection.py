"""Save the current selection as a channel in the active Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def save_selection(channel_name: str, **kwargs) -> dict:
    """Save the current selection as an alpha channel.

    Args:
        channel_name: Name for the saved channel. If None or empty, Photoshop
            assigns a default name.

    Returns:
        dict: ActionResultModel confirming the selection was saved.
    """
    app = Photoshop()

    return action_result(
        f"Saved selection as channel '{channel_name}'",
        lambda: _do_save_selection(app, channel_name),
        prompt="Use get_selection to verify bounds, or deselect to clear the active selection.",
    )


def _do_save_selection(app: Photoshop, channel_name: str) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    doc.selection.save(channel_name)

    return {"saved": True, "channel_name": channel_name}


def main(**kwargs) -> dict:
    """Entry point; delegates to save_selection."""
    return save_selection(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
