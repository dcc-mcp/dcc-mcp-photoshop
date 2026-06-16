"""Execute a named Photoshop Action via batchPlay."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def execute_action(action: str, action_set: str = "Default", **kwargs) -> dict:
    """Execute a Photoshop Action from an Action Set.

    Args:
        action: Name of the Action to execute.
        action_set: Name of the Action Set containing the Action. Default ``"Default"``.

    Returns:
        dict: ActionResultModel confirming execution.
    """
    app = Photoshop()

    return action_result(
        f"Executed action '{action}' from set '{action_set}'",
        lambda: _run_action(app, action, action_set),
        prompt=f"Action '{action}' has been executed.",
    )


def _run_action(app: Photoshop, action: str, action_set: str) -> dict:
    app.batch_play(
        [
            {
                "_obj": "play",
                "_target": [{"_ref": "action", "_name": action}],
                "using": {"_ref": "actionSet", "_name": action_set},
            }
        ],
        modal=True,
        command_name=f"Play action '{action}'",
    )
    return {"action": action, "action_set": action_set}


def main(**kwargs) -> dict:
    return execute_action(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
