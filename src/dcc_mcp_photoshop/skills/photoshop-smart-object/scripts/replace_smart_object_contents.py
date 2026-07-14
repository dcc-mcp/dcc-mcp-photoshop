"""Replace the contents of the active smart object with a file."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def replace_smart_object_contents(path: str, **kwargs) -> dict:
    """Replace the contents of the active smart object with an external file.

    Args:
        path: Path to the replacement file (e.g. ``"C:/images/new.psd"``).

    Returns:
        dict: ActionResultModel confirming the replacement.
    """
    app = Photoshop()

    return action_result(
        f"Replaced smart object contents with '{path}'",
        lambda: _replace_smart_object_contents(app, path),
        prompt="The smart object contents have been updated from the external file.",
    )


def _replace_smart_object_contents(app: Photoshop, path: str) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = app.activeLayer
    if layer is None:
        return {"error": "No active layer"}

    so = layer.smart_object
    so.replace_contents(path)

    return {
        "replaced": True,
        "layer_name": layer.name,
        "source_path": path,
    }


def main(**kwargs) -> dict:
    return replace_smart_object_contents(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
