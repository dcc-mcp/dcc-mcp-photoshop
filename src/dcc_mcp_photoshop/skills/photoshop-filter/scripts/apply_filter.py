"""Apply a generic filter from the filter namespace to the active Photoshop layer."""

from __future__ import annotations

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def apply_filter(
    method: str,
    **kwargs,
) -> dict:
    """Apply a named filter from the FiltersProxy namespace to the active layer.

    Use this as a generic entry point for any filter method available on
    ``layer.filters``.  For strongly-typed wrappers, prefer the dedicated
    scripts (``apply_gaussian_blur``, ``apply_sharpen``, etc.).

    Args:
        method: Name of the filter method on ``layer.filters``
            (e.g. ``"apply_gaussian_blur"``).
        **kwargs: Keyword arguments forwarded to the filter method.

    Returns:
        dict: ActionResultModel with filter name and parameters.
    """
    app = Photoshop()

    return action_result(
        f"Applied filter '{method}'",
        lambda: _do_apply(app, method, **kwargs),
        prompt=f"Filter '{method}' applied. Check the result on the active layer.",
    )


def _do_apply(app: Photoshop, method: str, **kwargs) -> dict:
    doc = app.activeDocument
    if doc is None:
        return {"error": "No active document"}

    layer = doc.activeLayer
    filter_func = getattr(layer.filters, method, None)
    if filter_func is None:
        return {"error": f"Unknown filter method: {method}"}

    filter_func(**kwargs)

    return {"filter": method, "params": kwargs}


def main(**kwargs) -> dict:
    """Entry point; delegates to apply_filter."""
    return apply_filter(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
