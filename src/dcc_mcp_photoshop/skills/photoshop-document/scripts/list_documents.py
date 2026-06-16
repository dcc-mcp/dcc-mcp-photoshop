"""List all open Adobe Photoshop documents."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def list_documents(**kwargs) -> dict:
    """List all currently open Photoshop documents.

    Returns:
        dict: ActionResultModel with a list of open documents and their metadata.
    """
    app = Photoshop()

    return action_result(
        "Retrieved list of open documents",
        lambda: _list_docs(app),
        prompt="Use get_document_info for details on a specific document.",
    )


def _list_docs(app: Photoshop) -> dict:
    docs = app.documents
    if not docs:
        return {"count": 0, "documents": []}

    result = []
    for doc in docs:
        result.append(
            {
                "id": doc.id,
                "name": doc.name,
                "path": doc.path,
                "width": doc.width,
                "height": doc.height,
            }
        )
    return {"count": len(result), "documents": result}


def main(**kwargs) -> dict:
    return list_documents(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
