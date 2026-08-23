from __future__ import annotations

import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from dcc_mcp_photoshop.cli import _build_parser
from dcc_mcp_photoshop.config import PhotoshopMcpConfig
from dcc_mcp_photoshop.install_lifecycle import run_install_lifecycle
from dcc_mcp_photoshop.server import StartupState


def test_public_cli_exposes_a_secret_safe_cross_platform_install_plan(tmp_path: Path) -> None:
    host = tmp_path / "Adobe Photoshop 2024" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2024")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    secret = "never-serialize-this-token"
    env = os.environ.copy()
    env.update(
        {
            "ADOBEPY_CLI": str(adobepy_cli),
            "ADOBEPY_TOKEN": secret,
            "DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR": str(state_dir),
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dcc_mcp_photoshop",
            "install",
            "--json",
            "--dry-run",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["dcc_type"] == "photoshop"
    assert report["verb"] == "install"
    assert report["mode"] == "plan"
    assert report["exit_code"] == 0
    assert report["plan"]["host"]["version"] == "2024"
    assert report["plan"]["python"]["executable"] == sys.executable
    assert secret not in result.stdout
    assert not (state_dir / "receipts" / "photoshop.json").exists()


def test_upgrade_cli_leaves_python_unset_for_receipt_reuse() -> None:
    args = _build_parser().parse_args(["upgrade", "--json", "--dry-run"])

    assert args.python == ""


def test_install_stages_bridge_writes_redacted_receipt_and_requires_real_host_rpc(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    host = tmp_path / "Adobe Photoshop 2024" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2024")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    secret = "receipt-must-never-contain-this"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", secret)
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command, *, env, capture_output, text, timeout):
        calls.append((command, env))
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
        (destination / "adobepy.config.js").write_text(secret, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, '{"token_configured":true}', "")

    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=True,
            dry_run=False,
            dcc_path=str(host),
            python=sys.executable,
        ),
        external_runner=fake_run,
    )

    stdout = capsys.readouterr().out
    report = json.loads(stdout)
    receipt_path = state_dir / "receipts" / "photoshop.json"
    assert exit_code == 50, json.dumps(report, indent=2)
    assert report["status"] == "requires_restart"
    assert report["verify"]["directly_usable"] is False
    assert report["verify"]["failure_stage"] == "broker_health"
    assert len(report["next_steps"]) == 1
    assert "command" in report["next_steps"][0] or "file_edit" in report["next_steps"][0]
    assert (state_dir / "bridge" / "manifest.json").is_file()
    assert receipt_path.is_file()
    assert secret not in stdout
    assert secret not in receipt_path.read_text(encoding="utf-8")
    assert "--token" not in calls[0][0]
    assert calls[0][1]["ADOBEPY_TOKEN"] == secret


def test_install_is_usable_only_after_broker_session_and_real_photoshop_rpc(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "runtime-only-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, '{"token_configured":true}', "")

    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=True,
            dry_run=False,
            dcc_path=str(host),
            python=sys.executable,
        ),
        external_runner=fake_run,
        broker_probe=lambda *_: {"ok": True, "sessions": 1},
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0"},
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["status"] == "ok"
    assert report["verify"] == {
        "directly_usable": True,
        "failure_stage": None,
        "failure_reason": None,
    }
    assert report["next_steps"] == []


def test_status_verify_and_receipt_only_uninstall_round_trip(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "round-trip-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def live_broker(*_):
        return {"ok": True, "sessions": 1}

    def live_photoshop(*_):
        return {"ok": True, "version": "26.0"}

    install_args = Namespace(
        command="install",
        json=True,
        yes=True,
        dry_run=False,
        dcc_path=str(host),
        python=sys.executable,
    )
    assert (
        run_install_lifecycle(
            install_args,
            external_runner=fake_run,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
        )
        == 0
    )
    capsys.readouterr()

    monkeypatch.delenv("ADOBEPY_CLI")
    status_args = Namespace(command="status", json=True, yes=False, dry_run=False, dcc_path="", python=sys.executable)
    monkeypatch.delenv("ADOBEPY_TOKEN")
    assert run_install_lifecycle(status_args, broker_probe=live_broker, photoshop_probe=live_photoshop) == 0
    no_token_status = json.loads(capsys.readouterr().out)
    assert no_token_status["installed_state"] == "installed"
    assert no_token_status["verify"]["failure_stage"] == "authentication"

    monkeypatch.setenv("ADOBEPY_TOKEN", "round-trip-token")
    assert run_install_lifecycle(status_args, broker_probe=live_broker, photoshop_probe=live_photoshop) == 0
    status_report = json.loads(capsys.readouterr().out)
    assert status_report["installed_state"] == "installed"
    assert status_report["verify"]["directly_usable"] is True

    verify_args = Namespace(command="verify", json=True, yes=False, dry_run=False, dcc_path="", python=sys.executable)
    assert run_install_lifecycle(verify_args, broker_probe=live_broker, photoshop_probe=live_photoshop) == 0
    verify_report = json.loads(capsys.readouterr().out)
    assert verify_report["verify"]["directly_usable"] is True

    uninstall_args = Namespace(
        command="uninstall", json=True, yes=True, dry_run=False, dcc_path="", python=sys.executable
    )
    assert run_install_lifecycle(uninstall_args) == 0
    uninstall_report = json.loads(capsys.readouterr().out)
    assert uninstall_report["status"] == "ok"
    assert not (state_dir / "bridge").exists()
    assert not (state_dir / "receipts" / "photoshop.json").exists()


def test_status_rejects_a_receipt_without_a_manifest_digest(tmp_path: Path, monkeypatch, capsys) -> None:
    state_dir = tmp_path / "state"
    bridge_root = state_dir / "bridge"
    receipt_path = state_dir / "receipts" / "photoshop.json"
    bridge_root.mkdir(parents=True)
    receipt_path.parent.mkdir(parents=True)
    (bridge_root / "manifest.json").write_text("{}", encoding="utf-8")
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dcc_type": "photoshop",
                "bridge_root": str(bridge_root),
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    exit_code = run_install_lifecycle(
        Namespace(command="status", json=True, yes=False, dry_run=False, dcc_path="", python="")
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["installed_state"] == "partial"
    assert report["verify"]["failure_stage"] == "receipt_integrity"


def test_status_treats_malformed_receipt_json_as_partial_state(tmp_path: Path, monkeypatch, capsys) -> None:
    state_dir = tmp_path / "state"
    bridge_root = state_dir / "bridge"
    receipt_path = state_dir / "receipts" / "photoshop.json"
    bridge_root.mkdir(parents=True)
    receipt_path.parent.mkdir(parents=True)
    (bridge_root / "manifest.json").write_text("{}", encoding="utf-8")
    receipt_path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    exit_code = run_install_lifecycle(
        Namespace(command="status", json=True, yes=False, dry_run=False, dcc_path="", python="")
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["installed_state"] == "partial"
    assert report["verify"]["failure_stage"] == "receipt_integrity"


def test_failed_upgrade_restores_the_previous_receipt_backed_bridge(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "upgrade-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    generated_version = ["old"]

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(generated_version[0], encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def live_broker(*_):
        return {"ok": True, "sessions": 1}

    def live_photoshop(*_):
        return {"ok": True, "version": "26.0"}

    args = Namespace(
        command="install",
        json=True,
        yes=True,
        dry_run=False,
        dcc_path=str(host),
        python=sys.executable,
    )
    assert (
        run_install_lifecycle(
            args,
            external_runner=fake_run,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
        )
        == 0
    )
    capsys.readouterr()
    receipt_path = state_dir / "receipts" / "photoshop.json"
    old_receipt = receipt_path.read_text(encoding="utf-8")

    generated_version[0] = "new"
    real_replace = os.replace

    def fail_new_bridge_commit(source, destination):
        if ".bridge-stage-" in Path(source).name and Path(destination).name == "bridge":
            raise OSError("simulated atomic commit failure")
        return real_replace(source, destination)

    args.command = "upgrade"
    exit_code = run_install_lifecycle(
        args,
        external_runner=fake_run,
        broker_probe=live_broker,
        photoshop_probe=live_photoshop,
        atomic_replace=fail_new_bridge_commit,
    )
    capsys.readouterr()

    assert exit_code == 30
    assert (state_dir / "bridge" / "manifest.json").read_text(encoding="utf-8") == "old"
    assert receipt_path.read_text(encoding="utf-8") == old_receipt


def test_install_rejects_broker_url_credentials_without_serializing_them(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "safe-env-token")
    monkeypatch.setenv("ADOBEPY_BROKER_URL", "http://operator:broker-password@127.0.0.1:47391")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=False,
            dry_run=True,
            dcc_path=str(host),
            python=sys.executable,
        )
    )

    stdout = capsys.readouterr().out
    report = json.loads(stdout)
    assert exit_code == 10
    assert report["verify"]["failure_stage"] == "security"
    assert "broker-password" not in stdout


def test_runtime_configuration_never_invents_an_adobepy_token(monkeypatch) -> None:
    monkeypatch.delenv("ADOBEPY_TOKEN", raising=False)

    assert PhotoshopMcpConfig.from_env().broker_token == ""


def test_startup_failures_are_captured_without_secrets(tmp_path: Path, monkeypatch) -> None:
    secret = "bootstrap-secret"
    monkeypatch.setenv("ADOBEPY_TOKEN", secret)
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path))

    StartupState().set_failed("broker_connect", f"broker rejected {secret}")

    diagnostic_path = tmp_path / "bootstrap-errors.json"
    payload = diagnostic_path.read_text(encoding="utf-8")
    assert "broker_connect" in payload
    assert secret not in payload


def test_photoshop_discovery_uses_real_windows_and_macos_application_layouts(tmp_path: Path) -> None:
    from dcc_mcp_photoshop.install_discovery import discover_photoshop_executable

    windows_root = tmp_path / "Program Files" / "Adobe"
    windows_host = windows_root / "Adobe Photoshop 2024" / "Photoshop.exe"
    windows_host.parent.mkdir(parents=True)
    windows_host.write_bytes(b"")
    mac_root = tmp_path / "Applications"
    mac_host = (
        mac_root / "Adobe Photoshop 2025" / "Adobe Photoshop 2025.app" / "Contents" / "MacOS" / "Adobe Photoshop 2025"
    )
    mac_host.parent.mkdir(parents=True)
    mac_host.write_bytes(b"")

    assert discover_photoshop_executable("Windows", [windows_root]) == (windows_host, "2024")
    assert discover_photoshop_executable("Darwin", [mac_root]) == (mac_host, "2025")


def test_install_preflight_enforces_the_minimum_core_version(tmp_path: Path, monkeypatch, capsys) -> None:
    import dcc_mcp_photoshop.install_contract as contract

    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "core-floor-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    real_version = contract.importlib.metadata.version

    def old_core_version(name: str) -> str:
        return "0.19.44" if name == "dcc-mcp-core" else real_version(name)

    monkeypatch.setattr(contract.importlib.metadata, "version", old_core_version)
    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=False,
            dry_run=True,
            dcc_path=str(host),
            python=sys.executable,
        )
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 10
    assert report["verify"]["failure_stage"] == "core_version"


def test_install_plan_classifies_partial_state_as_repair(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    (state_dir / "bridge").mkdir(parents=True)
    (state_dir / "bridge" / "manifest.json").write_text("orphaned", encoding="utf-8")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "repair-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    assert (
        run_install_lifecycle(
            Namespace(
                command="install",
                json=True,
                yes=False,
                dry_run=True,
                dcc_path=str(host),
                python=sys.executable,
            )
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["installed_state"] == "partial"
    assert report["plan"]["action"] == "repair"


def test_upgrade_reuses_receipt_host_and_python_when_overrides_are_omitted(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "upgrade-receipt-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def live_broker(*_):
        return {"ok": True, "sessions": 1}

    def live_photoshop(*_):
        return {"ok": True, "version": "26.0"}

    install_args = Namespace(
        command="install",
        json=True,
        yes=True,
        dry_run=False,
        dcc_path=str(host),
        python=sys.executable,
    )
    assert (
        run_install_lifecycle(
            install_args,
            external_runner=fake_run,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
        )
        == 0
    )
    capsys.readouterr()

    upgrade_args = Namespace(
        command="upgrade",
        json=True,
        yes=True,
        dry_run=False,
        dcc_path="",
        python="",
    )
    assert (
        run_install_lifecycle(
            upgrade_args,
            external_runner=fake_run,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["plan"]["host"]["executable"] == str(host)
    assert report["plan"]["python"]["executable"] == sys.executable


def test_preflight_failure_returns_one_machine_executable_retry_step(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.delenv("ADOBEPY_TOKEN", raising=False)
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    assert (
        run_install_lifecycle(
            Namespace(
                command="install",
                json=True,
                yes=False,
                dry_run=True,
                dcc_path=str(host),
                python=sys.executable,
            )
        )
        == 10
    )

    report = json.loads(capsys.readouterr().out)
    assert len(report["next_steps"]) == 1
    assert report["next_steps"][0]["command"][0] == "dcc-mcp-photoshop"
    assert report["next_steps"][0]["id"] == "retry-install-plan"


def test_verify_stops_at_target_import_before_photoshop_rpc(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "import-order-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def live_broker(*_):
        return {"ok": True, "sessions": 1}

    def live_photoshop(*_):
        return {"ok": True, "version": "26.0"}

    install_args = Namespace(
        command="install",
        json=True,
        yes=True,
        dry_run=False,
        dcc_path=str(host),
        python=sys.executable,
    )
    assert (
        run_install_lifecycle(
            install_args,
            external_runner=fake_run,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
        )
        == 0
    )
    capsys.readouterr()

    photoshop_calls: list[bool] = []

    def must_not_probe_photoshop(*_):
        photoshop_calls.append(True)
        return {"ok": True}

    verify_args = Namespace(command="verify", json=True, yes=False, dry_run=False, dcc_path="", python="")
    exit_code = run_install_lifecycle(
        verify_args,
        python_probe=lambda *_: {"ok": False},
        broker_probe=live_broker,
        photoshop_probe=must_not_probe_photoshop,
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 40
    assert report["verify"]["failure_stage"] == "target_import"
    assert photoshop_calls == []


def test_external_installer_secret_output_is_discarded_before_commit(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = tmp_path / ("adobepy.exe" if os.name == "nt" else "adobepy")
    adobepy_cli.write_bytes(b"")
    state_dir = tmp_path / "state"
    secret = "external-output-secret"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", secret)
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    def leaking_runner(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, secret, "")

    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=True,
            dry_run=False,
            dcc_path=str(host),
            python=sys.executable,
        ),
        external_runner=leaking_runner,
    )

    stdout = capsys.readouterr().out
    assert exit_code == 30
    assert secret not in stdout
    assert not (state_dir / "bridge").exists()
    assert not (state_dir / "receipts" / "photoshop.json").exists()
