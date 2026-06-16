"""Close a document in Adobe Photoshop."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def close_document(document_id: int = None, save: bool = False, **kwargs) -> dict:
    """Close a Photoshop document.

    Args:
        document_id: Document ID to close.  If ``None``, closes the active document.
        save: If ``True``, saves changes before closing. Default ``False``.

    Returns:
        dict: ActionResultModel with the closed document name.
    """
    app = Photoshop()

    return action_result(
        "Closed Photoshop document",
        lambda: _close(app, document_id, save),
        prompt="Use list_documents to see remaining open documents.",
    )


def _close(app: Photoshop, document_id: int | None, save: bool) -> dict:
    doc = app.activeDocument
    if document_id is not None:
        for d in app.documents:
            if d.id == document_id:
                doc = d
                break

    if doc is None:
        return {"error": "No document to close"}

    name = doc.name
    save_option = "yes" if save else "no"
    app.batch_play(
        [
            {
                "_obj": "close",
                "_target": [
                    {"_ref": "document", "_id": doc.id}
                ],
                "saving": {"_enum": "yesNo", "_value": save_option},
            }
        ],
        modal=True,
        command_name=f"Close document '{name}'",
    )
    return {"document_name": name, "closed": True}


def main(**kwargs) -> dict:
    return close_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
