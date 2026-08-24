from __future__ import annotations

import importlib.resources
import json
import logging
import sys
import types

from dcc_mcp_photoshop import install_verification, runtime_probe
from dcc_mcp_photoshop.context_snapshot import PhotoshopContextSnapshotProvider


def _install_module(monkeypatch, name: str, **attributes: object) -> None:
    module = types.ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    monkeypatch.setitem(sys.modules, name, module)


def test_runtime_probe_redacts_token_and_endpoint_credentials(monkeypatch) -> None:
    secret = "runtime-probe-secret"
    broker_url = "http://operator:password@127.0.0.1:47391"
    monkeypatch.setenv("ADOBEPY_TOKEN", secret)

    def fail_urlopen(*_args, **_kwargs):
        raise RuntimeError(f"request {broker_url} rejected token {secret}")

    monkeypatch.setattr(runtime_probe, "urlopen", fail_urlopen)
    broker = runtime_probe.probe_broker(broker_url, timeout=0.1)

    class FakePhotoshop:
        def __init__(self, **_kwargs) -> None:
            pass

        @property
        def version(self) -> str:
            raise RuntimeError(f"host {broker_url} rejected token {secret}")

    _install_module(monkeypatch, "adobe.photoshop", Photoshop=FakePhotoshop)
    photoshop = runtime_probe.probe_photoshop(broker_url, timeout=0.1)

    rendered = f"{broker!r} {photoshop!r}"
    assert secret not in rendered
    assert "operator:password" not in rendered
    assert broker["error_type"] == "invalid_configuration"
    assert photoshop["error_type"] == "invalid_configuration"


def test_target_import_does_not_inherit_adobe_credentials(monkeypatch) -> None:
    monkeypatch.setenv("ADOBEPY_TOKEN", "broker-secret")
    monkeypatch.setenv("ADOBE_TOKEN", "adobe-secret")

    real_run = install_verification.subprocess.run

    def fake_run(command, *, env, capture_output, text, timeout):
        assert "ADOBEPY_TOKEN" not in env
        assert "ADOBE_TOKEN" not in env
        return real_run(
            command,
            env=env,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )

    monkeypatch.setattr(install_verification.subprocess, "run", fake_run)

    assert install_verification.probe_target_import(sys.executable, 1.0)["ok"] is True


def test_broker_probe_classifies_a_non_object_payload_without_raw_error(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return b"[]"

    monkeypatch.setattr(runtime_probe, "urlopen", lambda *_args, **_kwargs: Response())

    result = runtime_probe.probe_broker("http://127.0.0.1:47391", timeout=0.1)

    assert result == {"ok": False, "sessions": 0, "error_type": "invalid_payload"}


def test_broker_probe_keeps_ipv6_loopback_canonical(monkeypatch) -> None:
    seen_urls = []

    def fake_request(request, _timeout):
        seen_urls.append(request.full_url)
        if request.full_url.endswith("/health"):
            return {"status": "ok", "protocol": "jsonrpc-2.0", "sessions": 0}, None
        return [], None

    monkeypatch.setattr(runtime_probe, "_request_json", fake_request)

    result = runtime_probe.probe_broker("http://[::1]:47391", timeout=0.1)

    assert result["ok"] is True
    assert seen_urls == ["http://[::1]:47391/health", "http://[::1]:47391/v1/capabilities"]


def test_lifecycle_converts_unexpected_oserror_to_schema_valid_json(monkeypatch, capsys) -> None:
    from argparse import Namespace

    from jsonschema import Draft202012Validator

    import dcc_mcp_photoshop.install_lifecycle as lifecycle

    schema = json.loads(
        importlib.resources.read_text(
            "dcc_mcp_photoshop.schemas",
            "adapter-install-sop-v1.schema.json",
            encoding="utf-8",
        )
    )
    monkeypatch.setattr(
        lifecycle,
        "build_install_report",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("secret raw operating-system detail")),
    )

    exit_code = lifecycle.run_install_lifecycle(
        Namespace(command="install", json=True, yes=False, dry_run=True, dcc_path="", python="")
    )
    rendered = capsys.readouterr().out
    report = json.loads(rendered)

    assert exit_code == 30
    assert report["verify"]["failure_stage"] == "internal_error"
    assert report["verify"]["error_type"] == "os_error"
    assert "secret raw" not in rendered
    Draft202012Validator(schema).validate(report)


def test_lifecycle_classifies_missing_executable_without_a_traceback(monkeypatch, capsys) -> None:
    from argparse import Namespace

    import dcc_mcp_photoshop.install_lifecycle as lifecycle

    monkeypatch.setattr(
        lifecycle,
        "build_install_report",
        lambda **_kwargs: (_ for _ in ()).throw(FileNotFoundError("secret missing command")),
    )

    exit_code = lifecycle.run_install_lifecycle(
        Namespace(command="install", json=True, yes=False, dry_run=True, dcc_path="", python="")
    )
    rendered = capsys.readouterr().out
    report = json.loads(rendered)

    assert exit_code == 30
    assert report["verify"]["error_type"] == "invalid_executable"
    assert "secret missing command" not in rendered


def test_context_snapshot_redacts_failures_before_json_or_logs(monkeypatch, caplog) -> None:
    secret = "context-snapshot-secret"
    broker_url = "http://operator:password@127.0.0.1:47391"
    monkeypatch.setenv("ADOBEPY_TOKEN", secret)

    class FakeBrokerClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def capabilities(self):
            raise RuntimeError(f"request {broker_url} rejected token {secret}")

    _install_module(monkeypatch, "adobe.core.client", BrokerClient=FakeBrokerClient)

    with caplog.at_level(logging.DEBUG):
        snapshot = PhotoshopContextSnapshotProvider().collect(broker_url)

    rendered = f"{snapshot!r} {caplog.text}"
    assert secret not in rendered
    assert "operator:password" not in rendered
    assert "<redacted>" in rendered
