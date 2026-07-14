"""Execute arbitrary ActionDescriptor descriptors via the batchPlay interface."""

from __future__ import annotations

from typing import Any

from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def batch_play(
    descriptors: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
    **kwargs,
) -> dict:
    """Execute one or more ActionDescriptor descriptors via batchPlay.

    This is the lowest-level Photoshop automation interface.  Every
    Photoshop operation can be expressed as an ActionDescriptor array
    passed through batchPlay.

    Args:
        descriptors: List of ActionDescriptor dicts to execute.
        options: Optional UXP batchPlay options dictionary.
        **kwargs: Additional keyword arguments (reserved).

    Returns:
        dict: ActionResultModel with the raw batchPlay result.
    """
    app = Photoshop()

    return action_result(
        f"Executed {len(descriptors)} batchPlay descriptor(s)",
        lambda: _do_batch_play(app, descriptors, options),
        prompt="Descriptors executed. Check the document for changes.",
    )


def _do_batch_play(
    app: Photoshop,
    descriptors: list[dict[str, Any]],
    options: dict[str, Any] | None,
) -> dict:
    result = app.batch_play(descriptors, options, modal=True)

    return {
        "descriptor_count": len(descriptors),
        "result": result,
    }


def main(**kwargs) -> dict:
    """Entry point; delegates to batch_play."""
    return batch_play(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
