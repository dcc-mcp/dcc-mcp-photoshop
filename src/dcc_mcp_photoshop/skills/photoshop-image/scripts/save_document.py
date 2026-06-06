"""Save the active Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def save_document(**kwargs) -> dict:
    """Save the active Photoshop document in its current format.

    For unsaved new documents use ``export_document`` to write to a file.

    Returns:
        dict: ActionResultModel confirming the save.
    """
    app = Photoshop()

    return action_result(
        "Document saved",
        lambda: _save(app),
    )


def _save(app: Photoshop) -> dict:
    doc = app.activeDocument
    if doc is not None and doc.path:
        doc.save_as(doc.path, modal=True, command_name="Save document")
        return {"saved": True}

    app.batch_play(
        [{"_obj": "save", "_target": [{"_ref": "document", "_enum": "ordinal", "_value": "targetEnum"}]}],
        modal=True,
        command_name="Save document",
    )
    return {"saved": True}


def main(**kwargs) -> dict:
    return save_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
