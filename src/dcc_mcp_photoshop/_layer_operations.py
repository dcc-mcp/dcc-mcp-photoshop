"""Shared Photoshop layer mutation helpers."""

from __future__ import annotations

from typing import Any


def rename_layer_by_id(app: Any, layer_id: int | str, name: str) -> None:
    """Rename a layer by stable id and fail if Photoshop rejects the action."""
    app.batch_play(
        [
            {
                "_obj": "set",
                "_target": [{"_ref": "layer", "_id": layer_id}],
                "to": {"_obj": "layer", "name": name},
            }
        ],
        modal=True,
        command_name="Rename layer",
    )
