from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_legacy_powershell_installer_is_a_thin_canonical_cli_wrapper() -> None:
    script = (ROOT / "scripts" / "install_photoshop_connector.ps1").read_text(encoding="utf-8")

    assert "Invoke-CanonicalLifecycle" in script
    assert "dcc-mcp-photoshop" in script
    assert "$PLUGIN_FILE" not in script
    assert "Install-CcxPlugin" not in script


def test_root_install_runbook_documents_the_canonical_cross_platform_contract() -> None:
    guide = (ROOT / "install.md").read_text(encoding="utf-8")

    for heading in (
        "# Requirements",
        "# Supported versions",
        "# Agent quick path",
        "# Manual path",
        "# Verify",
        "# Upgrade",
        "# Uninstall",
        "# Troubleshooting",
    ):
        assert heading in guide
    for platform_name in ("Windows", "macOS", "Linux"):
        assert platform_name in guide
    for verb in ("install", "status", "verify", "uninstall", "upgrade"):
        assert f"dcc-mcp-photoshop {verb}" in guide
    for exit_code in ("0", "10", "20", "30", "40", "50"):
        assert f"`{exit_code}`" in guide
    assert "--token" not in guide
    assert "ADOBEPY_TOKEN" in guide
    assert "files copied" in guide.lower()
    assert "real Photoshop RPC" in guide


def test_all_public_and_skill_install_surfaces_route_to_install_md() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    distribution = (ROOT / "docs" / "distribution.md").read_text(encoding="utf-8")
    setup_skill = (ROOT / "src" / "dcc_mcp_photoshop" / "skills" / "photoshop-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    raw_url = "https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-photoshop/main/install.md"

    assert "install.md" in readme
    assert "dev-token" not in readme
    assert raw_url in distribution
    assert "canonical" in setup_skill.lower()
    assert "dcc-mcp-photoshop install --json" in setup_skill


def test_ci_runs_the_install_lifecycle_contract_smoke() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Install lifecycle contract smoke" in workflow
    assert "tests/test_install_lifecycle.py tests/test_install_docs.py" in workflow
