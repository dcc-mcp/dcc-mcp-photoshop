from __future__ import annotations

from unittest.mock import Mock

from dcc_mcp_photoshop._layer_operations import rename_layer_by_id


def test_rename_layer_by_id_uses_stable_layer_reference():
    app = Mock()

    rename_layer_by_id(app, 42, "Hero")

    app.batch_play.assert_called_once_with(
        [
            {
                "_obj": "set",
                "_target": [{"_ref": "layer", "_id": 42}],
                "to": {"_obj": "layer", "name": "Hero"},
            }
        ],
        modal=True,
        command_name="Rename layer",
    )
