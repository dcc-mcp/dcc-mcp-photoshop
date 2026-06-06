"""Show or hide a layer in the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop


@skill_entry
def set_layer_visibility(name: str, visible: bool, **kwargs) -> dict:
    """Show or hide a named layer.

    Args:
        name: Exact layer name.
        visible: ``True`` to show, ``False`` to hide.

    Returns:
        dict: ActionResultModel with the current visibility state.
    """
    app = Photoshop()

    return action_result(
        f"Layer '{name}' is now {'visible' if visible else 'hidden'}",
        lambda: _set_visibility(app, name, visible),
    )


def _set_visibility(app: Photoshop, name: str, visible: bool) -> dict:
    action = "show" if visible else "hide"
    app.batch_play(
        [{"_obj": action, "_target": [{"_ref": "layer", "_name": name}]}],
        modal=True,
        command_name=f"{'Show' if visible else 'Hide'} layer",
    )
    return {"layer_name": name, "visible": visible}


def main(**kwargs) -> dict:
    return set_layer_visibility(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
