from __future__ import annotations

import hashlib
import importlib.resources
import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from dcc_mcp_photoshop.cli import _build_parser
from dcc_mcp_photoshop.config import PhotoshopMcpConfig
from dcc_mcp_photoshop.install_contract import version_tuple
from dcc_mcp_photoshop.install_io import commit_bridge
from dcc_mcp_photoshop.install_lifecycle import run_install_lifecycle
from dcc_mcp_photoshop.install_verification import probe_target_import, verify_photoshop_rpc
from dcc_mcp_photoshop.server import StartupState


def _canonical_install_validator() -> Draft202012Validator:
    schema_text = importlib.resources.read_text(
        "dcc_mcp_photoshop.schemas",
        "adapter-install-sop-v1.schema.json",
        encoding="utf-8",
    )
    schema = json.loads(schema_text)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_packaged_install_schema_is_the_exact_core_contract() -> None:
    contents = importlib.resources.read_binary(
        "dcc_mcp_photoshop.schemas",
        "adapter-install-sop-v1.schema.json",
    )
    assert len(contents) == 4261
    assert hashlib.sha256(contents).hexdigest() == ("3ca25788439917b4d4c0617230a762f9797756b5b54f45c8c4149f975b90f904")
    assert b"\r\n" not in contents


def _bound_runtime_probes(host: Path, state_dir: Path):
    connected_at = 1_777_000_000_000
    host_start_identity = "test-host-start:12345"
    broker_start_identity = "test-broker-start:67890"
    broker_executable = Path(os.environ["ADOBEPY_CLI"]).resolve()
    broker_contents = broker_executable.read_bytes()
    host_contents = host.read_bytes()

    def broker_probe(*_):
        return {
            "ok": True,
            "sessions": 1,
            "broker_url": "http://127.0.0.1:47391",
            "identity": {
                "pid": 2424,
                "process_start_identity": broker_start_identity,
                "executable": str(broker_executable),
                "version": "0.6.2",
                "instance_id": "adobepy-test-instance",
            },
            "capabilities": [
                {
                    "target": "default",
                    "connectedAtEpochMs": connected_at,
                    "capabilities": {
                        "host": "photoshop",
                        "bridgeKind": "uxp",
                        "bridgeVersion": "0.6.2",
                        "hostVersion": "26.0",
                    },
                }
            ],
        }

    def photoshop_probe(*_):
        bridge_root = state_dir / "bridge"
        return {
            "ok": True,
            "version": "26.0",
            "identity": {
                "host": "photoshop",
                "bridge_kind": "uxp",
                "target": "default",
                "host_version": "26.0",
                "bridge_version": "0.6.2",
                "host_pid": 4242,
                "process_start_identity": host_start_identity,
                "process_executable": str(host.resolve()),
                "instance_id": "photoshop-test-instance",
                "profile_id": "photoshop-test-profile",
                "plugin_root": str(bridge_root.resolve()),
                "plugin_module_origin": str((bridge_root / "manifest.json").resolve()),
                "broker_url": "http://127.0.0.1:47391",
                "connected_at_epoch_ms": connected_at,
            },
        }

    def process_probe(_pid):
        if _pid == 2424:
            return {
                "ok": True,
                "executable": str(broker_executable),
                "process_start_identity": broker_start_identity,
                "bytes": len(broker_contents),
                "sha256": hashlib.sha256(broker_contents).hexdigest(),
            }
        return {
            "ok": True,
            "executable": str(host.resolve()),
            "process_start_identity": host_start_identity,
            "bytes": len(host_contents),
            "sha256": hashlib.sha256(host_contents).hexdigest(),
        }

    return broker_probe, photoshop_probe, process_probe


def _fake_adobepy_cli(root: Path, version: str = "0.6.2") -> Path:
    bundle = root / f"adobepy-{version}-windows-x64"
    executable = bundle / "bin" / ("adobepy.exe" if os.name == "nt" else "adobepy")
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"test-adobepy-runtime")
    (bundle / "package-manifest.json").write_text(
        json.dumps(
            {
                "name": "adobepy",
                "version": version,
                "runtime": "windows-x64" if os.name == "nt" else "test-runtime",
                "includes": ["bin/adobepy.exe" if os.name == "nt" else "bin/adobepy"],
            }
        ),
        encoding="utf-8",
    )
    return executable


@pytest.fixture(autouse=True)
def _trusted_install_artifact_test_doubles(monkeypatch, request) -> None:
    """Keep lifecycle tests host-free while production provenance stays fail-closed."""
    from dcc_mcp_photoshop import install_planning

    def fake_host_attestation(path: Path):
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return None
        valid_name = resolved.name.casefold() == "photoshop.exe" or bool(
            __import__("re").fullmatch(r"Adobe Photoshop 20[0-9]{2}", resolved.name, __import__("re").IGNORECASE)
        )
        if not resolved.is_file() or resolved.is_symlink() or not valid_name:
            return None
        return {
            "executable": str(resolved),
            "version": "26.0",
            "product": "Adobe Photoshop",
            "publisher": "Adobe Inc.",
            "signature": "test_double",
            "bytes": resolved.stat().st_size,
            "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        }

    monkeypatch.setattr(install_planning, "attest_photoshop_executable", fake_host_attestation)
    if request.node.name in {
        "test_self_authored_adobepy_manifest_cannot_authenticate_arbitrary_cli",
        "test_declared_adobepy_floor_cli_matches_the_official_checksum_release",
    }:
        return

    def fake_cli_attestation(path: Path | None, sdk_version: str | None):
        if path is None or sdk_version != "0.6.2":
            return None
        try:
            resolved = path.resolve(strict=True)
            manifest = resolved.parent.parent / "package-manifest.json"
            executable_bytes = resolved.read_bytes()
            manifest_bytes = manifest.read_bytes()
        except OSError:
            return None
        if resolved.name.casefold() not in {"adobepy", "adobepy.exe"} or resolved.parent.name != "bin":
            return None
        return {
            "executable": str(resolved),
            "version": sdk_version,
            "runtime": "test-runtime",
            "bytes": len(executable_bytes),
            "sha256": hashlib.sha256(executable_bytes).hexdigest(),
            "manifest_path": str(manifest.resolve()),
            "manifest_bytes": len(manifest_bytes),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "release_asset": "test-only-adobepy.zip",
            "release_asset_sha256": "0" * 64,
            "release_url": "https://github.com/dcc-mcp/adobepy/releases/tag/adobepy-v0.6.2",
            "provenance": "official_checksum_release",
        }

    monkeypatch.setattr(install_planning, "_adobepy_cli_identity", fake_cli_attestation)


def _bridge_stage_receipt(command: list[str]) -> str:
    destination_path = Path(command[command.index("--dest") + 1]).resolve()
    config_path = destination_path / "adobepy.config.js"
    if not config_path.exists():
        config_path.write_text("test-config", encoding="utf-8")
    destination = str(destination_path)
    return json.dumps(
        {
            "success": True,
            "host": "photoshop",
            "kind": "uxp",
            "destination": destination,
            "config": str(config_path),
            "token_configured": True,
        }
    )


def test_public_cli_exposes_a_secret_safe_cross_platform_install_plan(tmp_path: Path) -> None:
    host = tmp_path / "Adobe Photoshop 2024" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2024")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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

    assert result.returncode == 10, result.stderr
    report = json.loads(result.stdout)
    _canonical_install_validator().validate(report)
    assert report["schema_version"] == 1
    assert report["dcc_type"] == "photoshop"
    assert report["verb"] == "install"
    assert report["mode"] == "plan"
    assert report["exit_code"] == 10
    assert report["verify"]["failure_stage"] == "preflight"
    assert "product provenance" in report["verify"]["failure_reason"]
    assert report["plan"]["python"]["executable"] == str(Path(sys.executable).resolve())
    assert secret not in result.stdout
    assert not (state_dir / "receipts" / "photoshop.json").exists()


def test_upgrade_cli_leaves_python_unset_for_receipt_reuse() -> None:
    args = _build_parser().parse_args(["upgrade", "--json", "--dry-run"])

    assert args.python == ""


def test_version_parser_accepts_only_bounded_final_release_values() -> None:
    assert version_tuple("0.20.14") == (0, 20, 14)
    assert version_tuple("2025") == (2025,)
    for value in (
        "",
        " 0.20.14",
        "0.20.14 ",
        "0.20.14rc1",
        "0.20.14garbage",
        "00.20.14",
        "0.020.14",
        "1.2.3.4.5",
        "9" * 128,
    ):
        assert version_tuple(value) == (), value


def test_runtime_identity_rejects_an_unbounded_target(monkeypatch) -> None:
    monkeypatch.setenv("ADOBEPY_TARGET", "x" * 129)

    result = verify_photoshop_rpc(
        "http://127.0.0.1:47391",
        python_executable=sys.executable,
        python_probe=lambda *_: {
            "ok": True,
            "python_executable": str(Path(sys.executable).resolve()),
            "modules": {
                key: {"distribution": distribution, "version": "1.0", "module_path": __file__, "owned": True}
                for key, distribution in {
                    "adapter": "dcc-mcp-photoshop",
                    "core": "dcc-mcp-core",
                    "adobepy": "adobepy",
                }.items()
            },
        },
        broker_probe=lambda *_: {
            "ok": True,
            "identity": {
                "pid": 1,
                "version": "1.0",
                "executable": sys.executable,
                "process_start_identity": "start",
                "instance_id": "instance",
            },
            "capabilities": [],
        },
        process_probe=lambda _pid: {
            "ok": True,
            "executable": sys.executable,
            "process_start_identity": "start",
        },
    )

    assert result["error_type"] == "invalid_configuration"


def test_target_import_rejects_a_shadow_adapter_module(tmp_path: Path, monkeypatch) -> None:
    shadow = tmp_path / "dcc_mcp_photoshop"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("SHADOW = True\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    result = probe_target_import(sys.executable, 5.0)

    assert result == {"ok": False, "error_type": "untrusted_module_origin"}


def test_target_import_binds_the_installed_core_schema_resource() -> None:
    result = probe_target_import(sys.executable, 5.0)

    assert result["ok"] is True
    assert result["core_schema"] == {
        "id": "https://dcc-mcp.github.io/schemas/adapter-install-sop-v1.schema.json",
        "size": 4261,
        "sha256": "3ca25788439917b4d4c0617230a762f9797756b5b54f45c8c4149f975b90f904",
        "record_owned": True,
    }


def test_verify_rejects_unbound_broker_and_photoshop_success_payloads() -> None:
    result = verify_photoshop_rpc(
        "http://127.0.0.1:47391",
        python_executable=sys.executable,
        python_probe=lambda *_: {"ok": True},
        broker_probe=lambda *_: {"ok": True, "sessions": 1},
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0"},
    )

    assert result["directly_usable"] is False
    assert result["failure_stage"] in {"target_import_identity", "broker_identity", "photoshop_identity"}


def test_verify_binds_exact_photoshop_uxp_process_and_module_identity(tmp_path: Path) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / "Photoshop.exe"
    host.parent.mkdir()
    host.write_bytes(b"host")
    bridge_root = tmp_path / "bridge"
    bridge_root.mkdir()
    module_origin = bridge_root / "index.js"
    module_origin.write_text("bridge", encoding="utf-8")
    broker_executable = tmp_path / "adobepy.exe"
    broker_executable.write_bytes(b"broker")
    modules = {
        key: {
            "distribution": distribution,
            "version": "1.2.3",
            "module_path": str(tmp_path / f"{key}.py"),
            "owned": True,
        }
        for key, distribution in {
            "adapter": "dcc-mcp-photoshop",
            "core": "dcc-mcp-core",
            "adobepy": "adobepy",
        }.items()
    }
    selected_python = str(Path(sys.executable).resolve())
    python_identity = {"ok": True, "python_executable": selected_python, "modules": modules}
    connected_at = 1_777_000_000_000
    broker_identity = {
        "ok": True,
        "sessions": 1,
        "broker_url": "http://127.0.0.1:47391",
        "identity": {
            "pid": 2424,
            "process_start_identity": "windows-filetime:broker",
            "executable": str(broker_executable),
            "version": "0.6.2",
            "instance_id": "adobepy-instance-1",
        },
        "capabilities": [
            {
                "target": "default",
                "connectedAtEpochMs": connected_at,
                "capabilities": {
                    "host": "photoshop",
                    "bridgeKind": "uxp",
                    "bridgeVersion": "0.6.2",
                    "hostVersion": "26.0",
                },
            }
        ],
    }
    identity = {
        "host": "photoshop",
        "bridge_kind": "uxp",
        "target": "default",
        "host_version": "26.0",
        "bridge_version": "0.6.2",
        "host_pid": 4242,
        "process_start_identity": "windows-filetime:12345",
        "process_executable": str(host),
        "instance_id": "photoshop-instance-1",
        "profile_id": "photoshop-profile-1",
        "plugin_root": str(bridge_root),
        "plugin_module_origin": str(module_origin),
        "broker_url": "http://127.0.0.1:47391",
        "connected_at_epoch_ms": connected_at,
    }
    process_identity = {
        "ok": True,
        "executable": str(host),
        "process_start_identity": "windows-filetime:12345",
    }

    def process_probe(pid):
        if pid == 2424:
            return {
                "ok": True,
                "executable": str(broker_executable),
                "process_start_identity": "windows-filetime:broker",
            }
        return process_identity

    result = verify_photoshop_rpc(
        "http://127.0.0.1:47391",
        python_executable=selected_python,
        expected_host={"executable": str(host), "version": "26.0"},
        expected_bridge={"installer": str(broker_executable), "installer_version": "0.6.2"},
        expected_bridge_root=bridge_root,
        expected_python={"executable": selected_python, "modules": modules},
        python_probe=lambda *_: python_identity,
        broker_probe=lambda *_: broker_identity,
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0", "identity": identity},
        process_probe=process_probe,
    )
    assert result["directly_usable"] is True

    wrong_product_version = verify_photoshop_rpc(
        "http://127.0.0.1:47391",
        python_executable=selected_python,
        expected_host={"executable": str(host), "version": "25.0"},
        expected_bridge={"installer": str(broker_executable), "installer_version": "0.6.2"},
        expected_bridge_root=bridge_root,
        expected_python={"executable": selected_python, "modules": modules},
        python_probe=lambda *_: python_identity,
        broker_probe=lambda *_: broker_identity,
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0", "identity": identity},
        process_probe=process_probe,
    )
    assert wrong_product_version["error_type"] == "wrong_host_version"

    observations = iter(
        [
            process_identity,
            {**process_identity, "process_start_identity": "windows-filetime:reused"},
        ]
    )

    def stale_process_probe(pid):
        return process_probe(pid) if pid == 2424 else next(observations)

    stale = verify_photoshop_rpc(
        "http://127.0.0.1:47391",
        python_executable=selected_python,
        expected_host={"executable": str(host), "version": "26.0"},
        expected_bridge={"installer": str(broker_executable), "installer_version": "0.6.2"},
        expected_bridge_root=bridge_root,
        expected_python={"executable": selected_python, "modules": modules},
        python_probe=lambda *_: python_identity,
        broker_probe=lambda *_: broker_identity,
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0", "identity": identity},
        process_probe=stale_process_probe,
    )
    assert stale["directly_usable"] is False
    assert stale["error_type"] == "process_identity_mismatch"


def test_install_stages_bridge_writes_redacted_receipt_and_requires_real_host_rpc(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    host = tmp_path / "Adobe Photoshop 2024" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2024")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

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
    _canonical_install_validator().validate(report)
    receipt_path = state_dir / "receipts" / "photoshop.json"
    assert exit_code == 50, json.dumps(report, indent=2)
    assert report["status"] == "requires_restart"
    assert report["verify"]["directly_usable"] is False
    assert report["verify"]["failure_stage"] == "broker_health"
    assert report["next_steps"] == []
    assert report["blocker"]["reason"] == "bounded_photoshop_uxp_bootstrap_unavailable"
    assert report["blocker"]["continuation_command"] == ["dcc-mcp-photoshop", "verify", "--json"]
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
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "runtime-only-token")
    state_dir = tmp_path / "state"
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))
    broker_probe, photoshop_probe, process_probe = _bound_runtime_probes(host, state_dir)

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

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
        broker_probe=broker_probe,
        photoshop_probe=photoshop_probe,
        process_probe=process_probe,
    )

    report = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(report)
    assert exit_code == 0
    assert report["status"] == "ok"
    assert report["verify"] == {
        "directly_usable": True,
        "failure_stage": None,
        "failure_reason": None,
        "error_type": None,
    }
    assert report["next_steps"] == []


def test_status_verify_and_receipt_only_uninstall_round_trip(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "round-trip-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)

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
            process_probe=process_probe,
        )
        == 0
    )
    capsys.readouterr()

    monkeypatch.delenv("ADOBEPY_CLI")
    status_args = Namespace(command="status", json=True, yes=False, dry_run=False, dcc_path="", python=sys.executable)
    monkeypatch.delenv("ADOBEPY_TOKEN")
    assert (
        run_install_lifecycle(
            status_args,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
            process_probe=process_probe,
        )
        == 0
    )
    no_token_status = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(no_token_status)
    assert no_token_status["installed_state"] == "installed"
    assert no_token_status["verify"]["failure_stage"] == "authentication"

    monkeypatch.setenv("ADOBEPY_TOKEN", "round-trip-token")
    assert (
        run_install_lifecycle(
            status_args,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
            process_probe=process_probe,
        )
        == 0
    )
    status_report = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(status_report)
    assert status_report["installed_state"] == "installed"
    assert status_report["verify"]["directly_usable"] is True

    verify_args = Namespace(command="verify", json=True, yes=False, dry_run=False, dcc_path="", python=sys.executable)
    assert (
        run_install_lifecycle(
            verify_args,
            broker_probe=live_broker,
            photoshop_probe=live_photoshop,
            process_probe=process_probe,
        )
        == 0
    )
    verify_report = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(verify_report)
    assert verify_report["verify"]["directly_usable"] is True

    uninstall_args = Namespace(
        command="uninstall", json=True, yes=True, dry_run=False, dcc_path="", python=sys.executable
    )
    assert run_install_lifecycle(uninstall_args) == 0
    uninstall_report = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(uninstall_report)
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


def test_unowned_empty_directory_blocks_status_and_uninstall(tmp_path: Path, monkeypatch, capsys) -> None:
    state_dir = tmp_path / "state"
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
    bridge_root = state_dir / "bridge"
    receipt_path = state_dir / "receipts" / "photoshop.json"
    status, error = commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={
            "schema_version": 1,
            "dcc_type": "photoshop",
            "bridge_root": str(bridge_root),
        },
    )
    assert (status, error) == ("ok", None)
    unowned = bridge_root / "operator-owned-empty"
    unowned.mkdir()
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    status_args = Namespace(command="status", json=True, yes=False, dry_run=False, dcc_path="", python="")
    assert run_install_lifecycle(status_args) == 0
    status_report = json.loads(capsys.readouterr().out)
    assert status_report["installed_state"] == "partial"

    uninstall_args = Namespace(command="uninstall", json=True, yes=True, dry_run=False, dcc_path="", python="")
    assert run_install_lifecycle(uninstall_args) == 10
    uninstall_report = json.loads(capsys.readouterr().out)
    assert uninstall_report["verify"]["failure_stage"] == "receipt_integrity"
    assert unowned.is_dir()
    assert receipt_path.is_file()


def test_receipt_rejects_duplicate_escape_wrong_type_and_tamper(tmp_path: Path) -> None:
    from copy import deepcopy

    from dcc_mcp_photoshop import install_io

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("{}", encoding="utf-8")
    (staging / "empty").mkdir()
    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    assert commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    ) == ("ok", None)
    receipt = install_io.load_receipt(receipt_path, bridge_root)
    assert receipt is not None and install_io.receipt_files_match(receipt, bridge_root)

    tampered_binding = deepcopy(receipt)
    tampered_binding["host"] = {"executable": "C:/foreign/Photoshop.exe", "version": "26.0"}
    receipt_path.write_text(json.dumps(tampered_binding), encoding="utf-8")
    assert install_io.load_receipt(receipt_path, bridge_root) is None
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    duplicate = deepcopy(receipt)
    duplicate["owned_entries"].append(deepcopy(duplicate["owned_entries"][0]))
    escape = deepcopy(receipt)
    escape["owned_entries"][0]["path"] = "../operator.txt"
    wrong_type = deepcopy(receipt)
    wrong_type["owned_entries"][0]["type"] = "socket"
    tampered = deepcopy(receipt)
    tampered["owned_entries"][0]["sha256"] = "0" * 64
    for invalid in (duplicate, escape, wrong_type, tampered):
        assert install_io.receipt_files_match(invalid, bridge_root) is False

    (bridge_root / "operator-owned.txt").write_text("keep", encoding="utf-8")
    assert install_io.receipt_files_match(receipt, bridge_root) is False


def test_owned_link_targets_are_bounded_to_the_install_root() -> None:
    from dcc_mcp_photoshop import install_io

    assert install_io._safe_symlink_target("assets/current.js", "../versions/bridge.js") is True
    for target in ("", "../operator.js", "../../operator.js", "/tmp/operator.js", "C:\\operator.js", "x" * 4097):
        assert install_io._safe_symlink_target("bridge.js", target) is False


@pytest.mark.skipif(os.name != "nt", reason="requires a native Windows directory junction")
def test_receipt_manifest_rejects_directory_junction_without_touching_target(tmp_path: Path) -> None:
    external = tmp_path / "operator-owned"
    external.mkdir()
    external_file = external / "do-not-own.txt"
    external_file.write_bytes(b"operator-owned-bytes")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("{}", encoding="utf-8")
    junction = staging / "external"
    created = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(external)],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip("native directory junction creation is unavailable")

    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    status, error = commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    )

    assert status == "failed", error
    assert external_file.read_bytes() == b"operator-owned-bytes"
    assert external.is_dir()
    assert not receipt_path.exists()


def test_uninstall_partial_cleanup_restores_complete_bridge_and_receipt(tmp_path: Path, monkeypatch) -> None:
    from dcc_mcp_photoshop import install_io

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
    (staging / "bridge.js").write_text("bridge", encoding="utf-8")
    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    assert commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    ) == ("ok", None)
    expected = {path.name: path.read_bytes() for path in bridge_root.iterdir() if path.is_file()}
    old_receipt = receipt_path.read_bytes()
    real_rmtree = shutil.rmtree

    def partial_remove(path, *args, **kwargs):
        candidate = Path(path)
        if ".uninstall-" in candidate.name:
            (candidate / "manifest.json").unlink()
            raise OSError("injected partial cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_io.shutil, "rmtree", partial_remove)

    status, error = install_io.remove_receipt_install(
        bridge_root=bridge_root,
        receipt_path=receipt_path,
    )

    assert status == "requires_restart", error
    assert {path.name: path.read_bytes() for path in bridge_root.iterdir() if path.is_file()} == expected
    assert receipt_path.read_bytes() == old_receipt
    receipt = install_io.load_receipt(receipt_path, bridge_root)
    assert receipt is not None and install_io.receipt_files_match(receipt, bridge_root)


def test_uninstall_snapshot_failure_never_removes_the_original_bridge(tmp_path: Path, monkeypatch) -> None:
    from dcc_mcp_photoshop import install_io

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("{}", encoding="utf-8")
    (staging / "bridge.js").write_text("bridge", encoding="utf-8")
    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    assert commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    ) == ("ok", None)
    expected = {path.name: path.read_bytes() for path in bridge_root.iterdir() if path.is_file()}
    old_receipt = receipt_path.read_bytes()
    real_copytree = shutil.copytree

    def fail_snapshot(source, destination, *args, **kwargs):
        if Path(source) == bridge_root:
            Path(destination).mkdir(parents=True)
            shutil.copy2(bridge_root / "manifest.json", Path(destination) / "manifest.json")
            raise OSError("injected snapshot failure")
        return real_copytree(source, destination, *args, **kwargs)

    monkeypatch.setattr(install_io.shutil, "copytree", fail_snapshot)
    status, error = install_io.remove_receipt_install(
        bridge_root=bridge_root,
        receipt_path=receipt_path,
    )

    assert status != "ok", error
    assert {path.name: path.read_bytes() for path in bridge_root.iterdir() if path.is_file()} == expected
    assert receipt_path.read_bytes() == old_receipt


def test_uninstall_receipt_delete_failure_restores_bridge(tmp_path: Path, monkeypatch) -> None:
    from dcc_mcp_photoshop import install_io

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text('{"id":"photoshop"}', encoding="utf-8")
    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    assert commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    ) == ("ok", None)
    old_receipt = receipt_path.read_bytes()
    real_unlink = Path.unlink

    def fail_receipt_unlink(path, *args, **kwargs):
        if path == receipt_path:
            raise OSError("injected receipt delete failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_receipt_unlink)

    status, error = install_io.remove_receipt_install(
        bridge_root=bridge_root,
        receipt_path=receipt_path,
    )

    assert status == "failed", error
    assert (bridge_root / "manifest.json").is_file()
    assert receipt_path.read_bytes() == old_receipt


def test_uninstall_never_reports_success_with_a_recovery_orphan(tmp_path: Path, monkeypatch) -> None:
    from dcc_mcp_photoshop import install_io

    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "manifest.json").write_text("{}", encoding="utf-8")
    bridge_root = tmp_path / "state" / "bridge"
    receipt_path = tmp_path / "state" / "receipts" / "photoshop.json"
    assert commit_bridge(
        staging=staging,
        destination=bridge_root,
        receipt_path=receipt_path,
        receipt={"schema_version": 1, "dcc_type": "photoshop", "bridge_root": str(bridge_root)},
    ) == ("ok", None)
    real_rmtree = shutil.rmtree

    def fail_recovery_cleanup(path, *args, **kwargs):
        if ".recovery-" in Path(path).name:
            raise OSError("injected recovery cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_io.shutil, "rmtree", fail_recovery_cleanup)
    status, error = install_io.remove_receipt_install(
        bridge_root=bridge_root,
        receipt_path=receipt_path,
    )

    assert status != "ok", error
    assert bridge_root.is_dir()
    assert receipt_path.is_file()


def test_failed_upgrade_restores_the_previous_receipt_backed_bridge(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "upgrade-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    generated_version = ["old"]

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(generated_version[0], encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)

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
            process_probe=process_probe,
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
        process_probe=process_probe,
        atomic_replace=fail_new_bridge_commit,
    )
    capsys.readouterr()

    assert exit_code == 30
    assert (state_dir / "bridge" / "manifest.json").read_text(encoding="utf-8") == "old"
    assert receipt_path.read_text(encoding="utf-8") == old_receipt


def test_upgrade_verification_failure_rolls_back_bridge_and_receipt(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "upgrade-verify-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))
    generated = ["old"]

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(generated[0], encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)

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
            process_probe=process_probe,
        )
        == 0
    )
    capsys.readouterr()
    receipt_path = state_dir / "receipts" / "photoshop.json"
    old_receipt = receipt_path.read_bytes()
    generated[0] = "new"
    args.command = "upgrade"

    exit_code = run_install_lifecycle(
        args,
        external_runner=fake_run,
        broker_probe=lambda *_: {"ok": False, "error_type": "connection_refused"},
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0"},
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 40
    _canonical_install_validator().validate(report)
    assert report["status"] == "failed"
    assert report["verify"]["failure_stage"] == "broker_health"
    assert (state_dir / "bridge" / "manifest.json").read_text(encoding="utf-8") == "old"
    assert receipt_path.read_bytes() == old_receipt
    assert not list(state_dir.glob(".bridge.*"))


def test_install_repair_verification_failure_restores_receipt_backed_bridge(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "install-repair-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))
    generated = ["old"]

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(generated[0], encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)
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
            process_probe=process_probe,
        )
        == 0
    )
    capsys.readouterr()
    receipt_path = state_dir / "receipts" / "photoshop.json"
    old_receipt = receipt_path.read_bytes()

    generated[0] = "new"
    exit_code = run_install_lifecycle(
        args,
        external_runner=fake_run,
        broker_probe=lambda *_: {"ok": False, "error_type": "connection_refused"},
        photoshop_probe=lambda *_: {"ok": True, "version": "26.0"},
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 40
    _canonical_install_validator().validate(report)
    assert report["status"] == "failed"
    assert report["previous_install_restored"] is True
    assert (state_dir / "bridge" / "manifest.json").read_text(encoding="utf-8") == "old"
    assert receipt_path.read_bytes() == old_receipt
    assert not list(state_dir.glob(".bridge.*"))


def test_install_rejects_broker_url_credentials_without_serializing_them(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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


def test_runtime_configuration_bounds_nonfinite_and_extreme_timeouts(monkeypatch) -> None:
    for value in ("nan", "inf", "-1", "0", "301", "garbage"):
        monkeypatch.setenv("DCC_MCP_PHOTOSHOP_TIMEOUT", value)
        assert PhotoshopMcpConfig.from_env().timeout == 30.0


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


def test_preflight_rejects_arbitrary_host_and_cli_executables(tmp_path: Path, monkeypatch, capsys) -> None:
    fake_host = tmp_path / "Adobe Photoshop 2025" / "not-photoshop.exe"
    fake_host.parent.mkdir()
    fake_host.write_bytes(b"host")
    fake_cli = tmp_path / "runner.exe"
    fake_cli.write_bytes(b"cli")
    monkeypatch.setenv("ADOBEPY_CLI", str(fake_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "preflight-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))

    exit_code = run_install_lifecycle(
        Namespace(
            command="install",
            json=True,
            yes=False,
            dry_run=True,
            dcc_path=str(fake_host),
            python=sys.executable,
        )
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 10
    assert report["verify"]["failure_stage"] == "preflight"
    assert report["plan"]["bridge"]["installer"] is None
    _canonical_install_validator().validate(report)


def test_install_preflight_enforces_the_minimum_core_version(tmp_path: Path, monkeypatch, capsys) -> None:
    import dcc_mcp_photoshop.install_contract as contract

    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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


def test_install_yes_refuses_an_unreceipted_partial_bridge_before_staging(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    bridge_root = state_dir / "bridge"
    bridge_root.mkdir(parents=True)
    operator_file = bridge_root / "operator-owned.txt"
    operator_file.write_bytes(b"keep-me")
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "partial-repair-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))
    staging_calls: list[list[str]] = []

    def fake_run(command, *, env, capture_output, text, timeout):
        staging_calls.append(command)
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("replacement", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

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
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 10
    _canonical_install_validator().validate(report)
    assert report["verify"]["failure_stage"] == "receipt_integrity"
    assert staging_calls == []
    assert operator_file.read_bytes() == b"keep-me"


def test_install_repair_rechecks_receipt_closure_after_external_staging(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "repair-race-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))
    generation = ["old"]
    stage_count = [0]

    def fake_run(command, *, env, capture_output, text, timeout):
        stage_count[0] += 1
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(generation[0], encoding="utf-8")
        if stage_count[0] == 2:
            (state_dir / "bridge" / "operator-owned.txt").write_bytes(b"keep-me")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)
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
            process_probe=process_probe,
        )
        == 0
    )
    capsys.readouterr()
    generation[0] = "new"

    exit_code = run_install_lifecycle(
        args,
        external_runner=fake_run,
        broker_probe=live_broker,
        photoshop_probe=live_photoshop,
        process_probe=process_probe,
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 10
    _canonical_install_validator().validate(report)
    assert report["verify"]["failure_stage"] == "receipt_integrity"
    assert (state_dir / "bridge" / "manifest.json").read_text(encoding="utf-8") == "old"
    assert (state_dir / "bridge" / "operator-owned.txt").read_bytes() == b"keep-me"


def test_upgrade_reuses_receipt_host_and_python_when_overrides_are_omitted(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "upgrade-receipt-token")
    state_dir = tmp_path / "state"
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)

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
            process_probe=process_probe,
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
            process_probe=process_probe,
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    _canonical_install_validator().validate(report)
    assert report["plan"]["host"]["executable"] == str(host)
    assert report["plan"]["python"]["executable"] == str(Path(sys.executable).resolve())


def test_preflight_missing_token_returns_an_honest_context_preserving_blocker(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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
    assert report["next_steps"] == []
    assert report["blocker"]["reason"] == "operator_broker_token_required"
    assert report["blocker"]["configuration"] == "ADOBEPY_TOKEN"
    assert report["blocker"]["continuation_command"] == [
        "dcc-mcp-photoshop",
        "install",
        "--json",
        "--dcc-path",
        str(host.resolve()),
        "--python",
        str(Path(sys.executable).resolve()),
        "--dry-run",
    ]


def test_verify_stops_at_target_import_before_photoshop_rpc(tmp_path: Path, monkeypatch, capsys) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "import-order-token")
    state_dir = tmp_path / "state"
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state_dir))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    live_broker, live_photoshop, process_probe = _bound_runtime_probes(host, state_dir)

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
            process_probe=process_probe,
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
    adobepy_cli = _fake_adobepy_cli(tmp_path)
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


def test_windows_host_attestation_uses_signed_product_metadata_not_the_filename(tmp_path: Path) -> None:
    from dcc_mcp_photoshop.install_discovery import attest_photoshop_executable

    host = tmp_path / "Adobe Photoshop 2024" / "Photoshop.exe"
    host.parent.mkdir(parents=True)
    host.write_bytes(b"signed-product-bytes")

    def valid_probe(command, **_kwargs):
        assert command[-1] == str(host.resolve())
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "status": "Valid",
                    "subject": "CN=Adobe Inc., O=Adobe Inc., C=US",
                    "company": "Adobe Inc.",
                    "product": "Adobe Photoshop",
                    "product_version": "26.4.0.0",
                }
            ),
            "",
        )

    identity = attest_photoshop_executable(host, platform_name="Windows", runner=valid_probe)

    assert identity is not None
    assert identity["version"] == "26.4.0.0"
    assert identity["product"] == "Adobe Photoshop"
    assert identity["publisher"] == "Adobe Inc."

    def wrong_signer(command, **_kwargs):
        payload = {
            "status": "Valid",
            "subject": "CN=Example Corp., O=Example Corp.",
            "company": "Adobe Inc.",
            "product": "Adobe Photoshop",
            "product_version": "26.4.0.0",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    assert attest_photoshop_executable(host, platform_name="Windows", runner=wrong_signer) is None

    def spoofed_signer_name(command, **_kwargs):
        payload = {
            "status": "Valid",
            "subject": "CN=Not Adobe Inc. Support, O=Example Corp.",
            "company": "Adobe Inc.",
            "product": "Adobe Photoshop",
            "product_version": "26.4.0.0",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    assert attest_photoshop_executable(host, platform_name="Windows", runner=spoofed_signer_name) is None


def test_host_attestation_rejects_zero_byte_and_symlink_spoofs(tmp_path: Path) -> None:
    from dcc_mcp_photoshop.install_discovery import attest_photoshop_executable

    zero = tmp_path / "Adobe Photoshop 2025" / "Photoshop.exe"
    zero.parent.mkdir(parents=True)
    zero.write_bytes(b"")
    assert attest_photoshop_executable(zero, platform_name="Windows") is None

    target = tmp_path / "real.exe"
    target.write_bytes(b"not-adobe")
    link = tmp_path / "Adobe Photoshop 2026" / "Photoshop.exe"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows test host")
    assert attest_photoshop_executable(link, platform_name="Windows") is None


def test_macos_host_attestation_binds_info_plist_and_adobe_team(tmp_path: Path) -> None:
    import plistlib

    from dcc_mcp_photoshop.install_discovery import attest_photoshop_executable

    bundle = tmp_path / "Adobe Photoshop 2025.app"
    host = bundle / "Contents" / "MacOS" / "Adobe Photoshop 2025"
    host.parent.mkdir(parents=True)
    host.write_bytes(b"signed-macos-product")
    info = bundle / "Contents" / "Info.plist"
    with info.open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleIdentifier": "com.adobe.Photoshop",
                "CFBundleName": "Adobe Photoshop 2025",
                "CFBundleExecutable": host.name,
                "CFBundleShortVersionString": "26.1.0",
            },
            stream,
        )

    def codesign_probe(command, **_kwargs):
        if "--verify" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(
            command,
            0,
            "",
            "Identifier=com.adobe.Photoshop\nTeamIdentifier=JQ525L2MZD\nAuthority=Developer ID Application: Adobe Inc.\n",
        )

    identity = attest_photoshop_executable(host, platform_name="Darwin", runner=codesign_probe)
    assert identity is not None
    assert identity["version"] == "26.1.0"
    assert identity["bundle_identifier"] == "com.adobe.Photoshop"
    assert identity["team_identifier"] == "JQ525L2MZD"

    def wrong_team(command, **_kwargs):
        if "--verify" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(
            command,
            0,
            "",
            "Identifier=com.adobe.Photoshop\nTeamIdentifier=EVILTEAM\nAuthority=Example Corp.\n",
        )

    assert attest_photoshop_executable(host, platform_name="Darwin", runner=wrong_team) is None


def test_self_authored_adobepy_manifest_cannot_authenticate_arbitrary_cli(tmp_path: Path) -> None:
    from dcc_mcp_photoshop.install_planning import _adobepy_cli_identity

    attacker_cli = _fake_adobepy_cli(tmp_path)

    assert _adobepy_cli_identity(attacker_cli, "0.6.2") is None


def test_declared_adobepy_floor_cli_matches_the_official_checksum_release() -> None:
    from dcc_mcp_photoshop.install_planning import _adobepy_cli_identity

    selected = os.environ.get("DCC_MCP_PHOTOSHOP_ADOBEPY_FLOOR_CLI")
    if not selected:
        pytest.skip("official adobepy CLI floor is supplied by the pinned CI job")

    identity = _adobepy_cli_identity(Path(selected), "0.6.2")

    assert identity is not None
    assert identity["bytes"] == 2_974_720
    assert identity["sha256"] == "c02f28f07705b69a4f97f9f6639f0f80d1f5292115446801fbd92423336301aa"
    assert identity["manifest_bytes"] == 663
    assert identity["manifest_sha256"] == "3f0cf14b44b1d4c7d98b0175152e7ea58fc3edb92bd61e84983b3ad39de6b554"
    assert identity["release_asset_sha256"] == ("9ef9abb5e034359f12e9ce248b0030e38d34c76df343eb2713f18036068719a7")


def test_stage_bridge_rejects_adobepy_cli_replacement_before_execution(tmp_path: Path) -> None:
    from dcc_mcp_photoshop.install_io import stage_bridge

    bundle = tmp_path / "adobepy-0.6.2-windows-x64"
    executable = bundle / "bin" / "adobepy.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"official-cli")
    manifest = bundle / "package-manifest.json"
    manifest.write_text("official-manifest", encoding="utf-8")
    expected_identity = {
        "executable": str(executable.resolve()),
        "bytes": len(b"official-cli"),
        "sha256": hashlib.sha256(b"official-cli").hexdigest(),
        "manifest_path": str(manifest.resolve()),
        "manifest_bytes": len(b"official-manifest"),
        "manifest_sha256": hashlib.sha256(b"official-manifest").hexdigest(),
        "provenance": "official_checksum_release",
    }
    executable.write_bytes(b"replaced-cli")
    calls = []

    staging, error = stage_bridge(
        executable=executable,
        expected_identity=expected_identity,
        state_dir=tmp_path / "state",
        token="secret",
        runner=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert staging is None
    assert error == "adobepy CLI identity changed before bridge staging"
    assert calls == []


def test_runtime_failure_returns_honest_uxp_bootstrap_blocker_not_doctor_loop(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    host = tmp_path / "Adobe Photoshop 2025" / ("Photoshop.exe" if os.name == "nt" else "Adobe Photoshop 2025")
    host.parent.mkdir(parents=True)
    host.write_bytes(b"signed-host-test-double")
    adobepy_cli = _fake_adobepy_cli(tmp_path)
    state = tmp_path / "state"
    monkeypatch.setenv("ADOBEPY_CLI", str(adobepy_cli))
    monkeypatch.setenv("ADOBEPY_TOKEN", "runtime-token")
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(state))

    def fake_run(command, *, env, capture_output, text, timeout):
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text("bridge", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, _bridge_stage_receipt(command), "")

    exit_code = run_install_lifecycle(
        Namespace(command="install", json=True, yes=True, dry_run=False, dcc_path=str(host), python=sys.executable),
        external_runner=fake_run,
        broker_probe=lambda *_: {"ok": False, "error_type": "broker_unavailable"},
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 50
    assert report["next_steps"] == []
    assert report["blocker"]["reason"] == "bounded_photoshop_uxp_bootstrap_unavailable"
    assert report["blocker"]["dependency_issue"].endswith("/dcc-mcp/adobepy/issues/67")
    assert report["blocker"]["continuation_command"] == ["dcc-mcp-photoshop", "verify", "--json"]


def test_repeated_absent_uninstall_is_a_schema_valid_successful_noop(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR", str(tmp_path / "state"))
    args = Namespace(command="uninstall", json=True, yes=True, dry_run=False, dcc_path="", python="")

    for _ in range(2):
        assert run_install_lifecycle(args) == 0
        report = json.loads(capsys.readouterr().out)
        _canonical_install_validator().validate(report)
        assert report["status"] == "ok"
        assert report["installed_state"] == "fresh"
        assert report["receipt_path"] is None
        assert report["steps"][-1] == {"id": "uninstall", "status": "not_installed"}
