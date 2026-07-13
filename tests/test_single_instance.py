from __future__ import annotations

from pathlib import Path

import pytest

from dcc_mcp_photoshop import cli
from dcc_mcp_photoshop._single_instance import AlreadyRunningError, SingleInstanceLease


def test_second_photoshop_sidecar_cannot_acquire_same_lease(tmp_path: Path):
    lock_path = tmp_path / "photoshop-sidecar.lock"

    with SingleInstanceLease(lock_path):
        with pytest.raises(AlreadyRunningError, match="already running"):
            with SingleInstanceLease(lock_path):
                pass


def test_photoshop_sidecar_lease_is_reusable_after_release(tmp_path: Path):
    lock_path = tmp_path / "photoshop-sidecar.lock"

    with SingleInstanceLease(lock_path):
        pass


def test_cli_rejects_second_photoshop_sidecar(tmp_path: Path, monkeypatch, capsys):
    lock_path = tmp_path / "photoshop-sidecar.lock"
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_LOCK_FILE", str(lock_path))

    with SingleInstanceLease(lock_path):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--mcp-port", "0"])

    assert exc_info.value.code == 1
    assert "already running" in capsys.readouterr().err

    with SingleInstanceLease(lock_path):
        pass
