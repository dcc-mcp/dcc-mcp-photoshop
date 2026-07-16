"""Open a local file as an Adobe Photoshop document."""

from __future__ import annotations

from pathlib import Path

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def open_document(path: str, **kwargs) -> dict:
    """Open an existing local image or Photoshop document."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        return {"success": False, "error": f"Document does not exist: {source}"}

    app = Photoshop()
    return action_result(
        f"Opened Photoshop document '{source.name}'",
        lambda: _open(app, source),
        prompt="Use create_text_layer, list_layers, or export_document to continue editing.",
    )


def _open(app: Photoshop, source: Path) -> dict:
    result = app.batch_play(
        [
            {
                "_obj": "open",
                "null": {"_path": str(source), "_kind": "local"},
                "_options": {"dialogOptions": "dontDisplay"},
            }
        ],
        modal=True,
        command_name=f"Open document '{source.name}'",
    )
    document = app.activeDocument
    if document is None:
        raise RuntimeError(f"Photoshop did not expose the opened document as active: {result!r}")
    return {
        "document_id": document.id,
        "document_name": document.name,
        "path": str(source),
        "width": document.width,
        "height": document.height,
    }


def main(**kwargs) -> dict:
    return open_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
