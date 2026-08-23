"""Contract tests for the Photoshop setup skill."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def _load_setup_module():
    path = (
        Path(__file__).parent.parent
        / "src"
        / "dcc_mcp_photoshop"
        / "skills"
        / "photoshop-setup"
        / "scripts"
        / "setup_uxp_plugin.py"
    )
    spec = importlib.util.spec_from_file_location("setup_uxp_plugin", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_verify_module():
    path = (
        Path(__file__).parent.parent
        / "src"
        / "dcc_mcp_photoshop"
        / "skills"
        / "photoshop-setup"
        / "scripts"
        / "verify_connection.py"
    )
    spec = importlib.util.spec_from_file_location("verify_connection", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_setup_tool_routes_to_the_canonical_install_contract(tmp_path: Path) -> None:
    module = _load_setup_module()
    result = module.setup_uxp_plugin(bridge_dir=str(tmp_path / "bridge"))

    assert result["success"] is True
    assert result["details"]["state"] == "canonical_redirect"
    assert result["next_steps"] == [
        {
            "id": "canonical-install",
            "description": "Run the canonical Photoshop install lifecycle",
            "command": ["dcc-mcp-photoshop", "install", "--json", "--yes"],
            "why": "The canonical lifecycle owns staging, receipts, rollback, and verify-to-usable",
        }
    ]


def test_legacy_setup_route_does_not_bypass_canonical_cli_preflight(tmp_path: Path) -> None:
    module = _load_setup_module()

    result = module.setup_uxp_plugin(bridge_dir=str(tmp_path / "bridge"))

    assert result["success"] is True
    assert result["details"]["state"] == "canonical_redirect"


def test_verify_requires_a_connected_bridge_session() -> None:
    module = _load_verify_module()
    with patch.object(module, "_check_tcp_endpoint", return_value={"ok": True}):
        with patch.object(module, "probe_broker", return_value={"ok": True, "sessions": 0}):
            with patch.object(module, "probe_photoshop") as photoshop:
                result = module.verify_connection()

    assert result["success"] is False
    assert result["details"]["photoshop"]["ok"] is False
    photoshop.assert_not_called()


def test_verify_executes_real_host_probe_after_broker_session_connects() -> None:
    module = _load_verify_module()
    with patch.object(module, "_check_tcp_endpoint", return_value={"ok": True}):
        with patch.object(module, "probe_broker", return_value={"ok": True, "sessions": 1}):
            with patch.object(module, "probe_photoshop", return_value={"ok": True, "version": "26.5"}) as photoshop:
                result = module.verify_connection(broker_url="http://broker:47391", timeout=3)

    assert result["success"] is True
    photoshop.assert_called_once_with("http://broker:47391", 3.0)
