"""Export the active Adobe Photoshop document to a file."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def export_document(
    path: str,
    format: str = "png",
    quality: int = 90,
    **kwargs,
) -> dict:
    """Export the active Photoshop document to a file.

    The file is written to the UXP plugin's temporary data folder when an
    arbitrary path cannot be accessed.  The actual output path is returned
    so the agent can report it to the user.

    Args:
        path: Desired output filename or path (e.g. ``"output.png"``).
            If the full path is not accessible via UXP, the file lands in
            the plugin PluginData temp directory.
        format: Output format: ``"png"`` (default), ``"jpg"``, ``"tiff"``,
            or ``"psd"``.
        quality: JPEG quality 0-100 (only for ``format="jpg"``).

    Returns:
        dict: ActionResultModel with the actual output path and format.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.exportDocument", path=path, format=format, quality=quality)

    out_path = result.get("path", path)
    return ps_success(
        f"Exported document as {format.upper()} → {out_path}",
        prompt="The file has been saved. Share the path with the user.",
        exported=result.get("exported", True),
        path=out_path,
        format=result.get("format", format),
    )


def main(**kwargs) -> dict:
    return export_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
