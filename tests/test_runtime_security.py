from __future__ import annotations

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
    assert "<redacted>" in rendered


def test_target_import_does_not_inherit_adobe_credentials(monkeypatch) -> None:
    monkeypatch.setenv("ADOBEPY_TOKEN", "broker-secret")
    monkeypatch.setenv("ADOBE_TOKEN", "adobe-secret")

    def fake_run(command, *, env, capture_output, text, timeout):
        assert "ADOBEPY_TOKEN" not in env
        assert "ADOBE_TOKEN" not in env
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(install_verification.subprocess, "run", fake_run)

    assert install_verification.probe_target_import(sys.executable, 1.0) == {"ok": True}


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
