"""Apply a ``.cube`` 3D LUT as a Color Lookup adjustment layer.

The LUT file is parsed and validated locally (via ``_color_lookup.parse_cube``)
before any host call, so a malformed file can never reach Photoshop. The native
color-lookup operation is expressed as a ``colorLookup`` adjustment-layer
ActionDescriptor passed through ``batchPlay``; the ``_color_lookup`` math module
also models the expected pixel transform for the offline regression suite.

Native end-to-end acceptance (real document load, pixel diff, toggle, export a
copy, reopen) still requires a deployed, authenticated broker and is a separate
gate; this tool does not fabricate native results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adobe.dcc_mcp import action_result, adobe_error
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry

from dcc_mcp_photoshop._color_lookup import is_identity, parse_cube

DEFAULT_LAYER_NAME = "Color Lookup"


def _build_descriptor(
    lut_path: str,
    *,
    enabled: bool,
    opacity: float,
    layer_name: str,
) -> dict[str, Any]:
    """Build the ``colorLookup`` adjustment-layer ActionDescriptor.

    Keys follow Photoshop's ActionDescriptor ``colorLookup`` conventions
    (``dataSource`` = ``LUT3DFile`` plus the local ``.cube`` path). Native
    pixel-level acceptance of this descriptor is a separate gate that requires
    a deployed broker; the offline suite only pins its structure.
    """
    return {
        "_obj": "make",
        "_target": [{"_ref": "adjustmentLayer"}],
        "using": {
            "_obj": "adjustmentLayer",
            "name": layer_name,
            "opacity": opacity,
            "enabled": enabled,
            "type": {
                "_obj": "colorLookup",
                "dataSource": {"_enum": "dataSource", "_value": "LUT3DFile"},
                "LUT3DFile": {"_path": lut_path, "_kind": "local"},
            },
        },
    }


def _do_apply(
    app: Photoshop,
    lut_path: str,
    *,
    enabled: bool,
    opacity: float,
    layer_name: str,
    identity: bool,
    lut_size: int,
) -> dict[str, Any]:
    descriptor = _build_descriptor(lut_path, enabled=enabled, opacity=opacity, layer_name=layer_name)
    result = app.batch_play([descriptor], modal=True)
    return {
        "lut_path": lut_path,
        "lut_filename": Path(lut_path).name,
        "lut_size": lut_size,
        "is_identity": identity,
        "enabled": enabled,
        "opacity": opacity,
        "layer_name": layer_name,
        "result": result,
    }


@skill_entry
def apply_color_lookup(
    lut_path: str,
    *,
    enabled: bool = True,
    opacity: float = 100.0,
    layer_name: str = DEFAULT_LAYER_NAME,
    **kwargs,
) -> dict:
    """Apply a ``.cube`` 3D LUT as a Color Lookup adjustment layer.

    Args:
        lut_path: Absolute path to a ``.cube`` 3D LUT file.
        enabled: Whether the adjustment layer is enabled (toggle support).
        opacity: Adjustment layer opacity in the range ``[0, 100]``.
        layer_name: Name for the new adjustment layer.
        **kwargs: Additional keyword arguments (reserved).

    Returns:
        dict: ActionResultModel with the LUT metadata and batchPlay result, or
        an error result when the LUT is missing or malformed.
    """
    path = Path(lut_path).expanduser()
    if not path.is_file():
        return adobe_error(f"LUT file not found: {path.name}", "LUT file not found")
    if path.suffix.lower() != ".cube":
        return adobe_error(f"Unsupported LUT file: {path.name}", "expected a .cube file")
    if not 0.0 <= opacity <= 100.0:
        return adobe_error("Invalid opacity", "opacity must be within [0, 100]")

    try:
        lut = parse_cube(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return adobe_error(f"Invalid .cube LUT: {path.name}", str(exc))

    identity = is_identity(lut)
    app = Photoshop()
    return action_result(
        f"Applied color lookup '{path.name}'",
        lambda: _do_apply(
            app,
            str(path),
            enabled=enabled,
            opacity=opacity,
            layer_name=layer_name,
            identity=identity,
            lut_size=lut.size,
        ),
        prompt="Color Lookup adjustment added. Verify on the active document.",
    )


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_color_lookup."""
    return apply_color_lookup(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
