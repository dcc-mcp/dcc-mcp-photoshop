"""Save the active Adobe Photoshop document."""

from __future__ import annotations

from dcc_mcp_core.skill import skill_entry


@skill_entry
def save_document(**kwargs) -> dict:
    """Save the active Photoshop document in its current format.

    For unsaved new documents use ``export_document`` to write to a file.

    Returns:
        dict: ActionResultModel confirming the save.
    """
    from dcc_mcp_photoshop.api import get_bridge, ps_success  # noqa: PLC0415

    bridge = get_bridge()
    result = bridge.call("ps.saveDocument")

    return ps_success(
        "Document saved",
        saved=result.get("saved", True),
    )


def main(**kwargs) -> dict:
    return save_document(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
