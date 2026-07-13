"""Contract tests for the Photoshop setup skill."""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_auto_stages_adobepy_bridge_without_claiming_host_install(tmp_path: Path) -> None:
    module = _load_setup_module()
    executable = str(tmp_path / "adobepy.exe")

    with patch.object(module.shutil, "which", return_value=executable):
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as run:
            result = module.setup_uxp_plugin(bridge_dir=str(tmp_path / "bridge"))

    assert result["success"] is True
    assert result["details"]["state"] == "staged"
    assert "UXP Developer Tool" in result["prompt"]
    run.assert_called_once_with(
        [executable, "install-bridge", "photoshop", "--dest", str(tmp_path / "bridge")],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_auto_fails_closed_when_adobepy_cli_is_missing(tmp_path: Path) -> None:
    module = _load_setup_module()

    with patch.object(module.shutil, "which", return_value=None):
        result = module.setup_uxp_plugin(bridge_dir=str(tmp_path / "bridge"))

    assert result["success"] is False
    assert result["details"]["state"] == "not_staged"
    assert "adobepy" in result["summary"]


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
