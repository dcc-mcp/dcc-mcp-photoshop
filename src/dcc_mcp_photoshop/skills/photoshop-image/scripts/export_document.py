"""Export the active Adobe Photoshop document to a file."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def export_document(
    path: str,
    format: str = "png",
    quality: int = 90,
    **kwargs,
) -> dict:
    """Export the active Photoshop document to a file.

    Args:
        path: Desired output filename or path (e.g. ``"output.png"``).
        format: Output format: ``"png"`` (default), ``"jpg"``, ``"tiff"``,
            or ``"psd"``.
        quality: JPEG quality 0-100 (only for ``format="jpg"``).

    Returns:
        dict: ActionResultModel with the actual output path and format.
    """
    app = Photoshop()

    return action_result(
        f"Exported document as {format.upper()} → {path}",
        lambda: _export(app, path, format, quality),
        prompt="The file has been saved. Share the path with the user.",
    )


def _export(app: Photoshop, path: str, format: str, quality: int) -> dict:
    options = {}
    if format == "jpg":
        options["quality"] = quality
        options["format"] = "jpg"
    elif format == "tiff":
        options["format"] = "tiff"

    if app.activeDocument:
        result = app.activeDocument.export(path, format=format, options=options)
        out_path = result.get("path", path) if isinstance(result, dict) else path
        return {"exported": True, "path": out_path, "format": format}

    app.batch_play(
        [{"_obj": "export", "using": {"_obj": f"{format.upper()}Format", "path": path}}],
        modal=True,
        command_name="Export document",
    )
    return {"exported": True, "path": path, "format": format}


def main(**kwargs) -> dict:
    return export_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
