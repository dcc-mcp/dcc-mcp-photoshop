"""Static contracts for bundled Photoshop skills."""

from __future__ import annotations

from pathlib import Path

import yaml

SKILLS_ROOT = Path(__file__).parents[1] / "src" / "dcc_mcp_photoshop" / "skills"


def test_bundled_tools_have_static_input_schemas():
    for tools_file in sorted(SKILLS_ROOT.glob("*/tools.yaml")):
        payload = yaml.safe_load(tools_file.read_text(encoding="utf-8"))
        for tool in payload["tools"]:
            schema = tool.get("input_schema")
            assert schema is not None, f"{tools_file.parent.name}.{tool['name']} has no input_schema"
            assert schema.get("type") == "object"
            source_file = tools_file.parent / tool["source_file"]
            assert source_file.is_file(), f"Missing source file: {source_file}"
