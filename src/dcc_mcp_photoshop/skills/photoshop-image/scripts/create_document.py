"""Create a new Adobe Photoshop document."""

from __future__ import annotations

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
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call(
        "ps.createDocument",
        name=name,
        width=width,
        height=height,
        resolution=resolution,
        color_mode=color_mode,
        bit_depth=bit_depth,
        fill=fill,
    )

    return ps_success(
        f"Created document '{result.get('name', name)}' ({width}×{height}px)",
        prompt="Use create_layer or add text layers to start compositing.",
        document_id=result.get("id"),
        document_name=result.get("name", name),
        width=width,
        height=height,
        resolution=resolution,
        color_mode=color_mode,
    )


def main(**kwargs) -> dict:
    return create_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
