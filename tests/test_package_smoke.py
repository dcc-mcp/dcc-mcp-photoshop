from __future__ import annotations

import importlib.resources
import subprocess
import sys
from pathlib import Path


def test_package_metadata_exposes_bounded_install_dependencies() -> None:
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert '"adobepy==0.6.2"' in pyproject
    assert '"dcc-mcp-core>=0.20.14,<1.0.0"' in pyproject


def test_packaged_schema_and_setup_skill_are_present() -> None:
    schema = importlib.resources.read_binary("dcc_mcp_photoshop.schemas", "adapter-install-sop-v1.schema.json")
    skill = Path(__file__).parents[1] / "src" / "dcc_mcp_photoshop" / "skills" / "photoshop-setup" / "SKILL.md"

    assert len(schema) == 4_261
    assert skill.is_file()
    assert "dcc-mcp-photoshop verify --json" in skill.read_text(encoding="utf-8")


def test_cli_package_entrypoint_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dcc_mcp_photoshop", "--help"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "dcc-mcp-photoshop" in result.stdout
    assert "install" in result.stdout
