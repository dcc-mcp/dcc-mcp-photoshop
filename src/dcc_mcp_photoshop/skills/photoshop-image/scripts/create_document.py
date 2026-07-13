"""Create a new Adobe Photoshop document."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def create_document(
    name: str = "Untitled",
    width: int = 1920,
    height: int = 1080,
    resolution: float = 72.0,
    color_mode: str = "rgb",
    bit_depth: int = 8,
    fill: str = "white",
    **kwargs,
) -> dict:
    """Create a new Photoshop document.

    Args:
        name: Document name (default ``"Untitled"``).
        width: Canvas width in pixels (default 1920).
        height: Canvas height in pixels (default 1080).
        resolution: Resolution in PPI (default 72).
        color_mode: ``"rgb"`` (default), ``"cmyk"``, ``"grayscale"``, or ``"lab"``.
        bit_depth: Bits per channel: ``8`` (default), ``16``, or ``32``.
        fill: Initial fill: ``"white"`` (default), ``"black"``,
            ``"transparent"``, or ``"background"``.

    Returns:
        dict: ActionResultModel with the new document id and metadata.
    """
    app = Photoshop()

    return action_result(
        f"Created document '{name}' ({width}×{height}px)",
        lambda: _create_document(app, name, width, height, resolution, color_mode, bit_depth, fill),
        prompt="Use create_layer or add text layers to start compositing.",
    )


def _create_document(
    app: Photoshop, name: str, width: int, height: int, resolution: float, color_mode: str, bit_depth: int, fill: str
) -> dict:
    result = app.dom.app.documents.add(
        {
            "name": name,
            "width": width,
            "height": height,
            "resolution": resolution,
            "mode": _map_color_mode(color_mode),
            "depth": bit_depth,
            "fill": _map_fill(fill),
        },
        modal=True,
        command_name="Create document",
    )
    if not isinstance(result, dict) or result.get("id") is None:
        raise RuntimeError(f"Photoshop did not create the document: {result!r}")
    return {
        "document_id": result["id"],
        "document_name": result.get("name", name),
        "width": result.get("width", width),
        "height": result.get("height", height),
        "resolution": result.get("resolution", resolution),
        "color_mode": color_mode,
    }


def _map_color_mode(mode: str) -> str:
    mapping = {
        "rgb": "RGBColorMode",
        "cmyk": "CMYKColorMode",
        "grayscale": "grayscaleMode",
        "lab": "labColorMode",
    }
    return mapping.get(mode, "RGBColorMode")


def _map_fill(fill: str) -> str:
    mapping = {
        "white": "white",
        "black": "black",
        "transparent": "transparent",
        "background": "backgroundColor",
    }
    return mapping.get(fill, "white")


def main(**kwargs) -> dict:
    return create_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
