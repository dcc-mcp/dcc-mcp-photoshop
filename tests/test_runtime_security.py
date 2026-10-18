from __future__ import annotations

import ctypes
import importlib.resources
import json
import logging
import sys
import types
from dataclasses import dataclass

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

    # The probe spawns an interpreter that imports adobe, dcc-mcp-core and this adapter.
    # A 1s budget was below cold-start cost on a loaded runner and made this test flaky.
    assert install_verification.probe_target_import(sys.executable, 30.0)["ok"] is True


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
    # Identity is fetched last and is best-effort: a non-object broker-identity
    # payload leaves identity None without failing liveness.
    assert seen_urls == [
        "http://[::1]:47391/health",
        "http://[::1]:47391/v1/capabilities",
        "http://[::1]:47391/v1/broker-identity",
    ]
    assert result["identity"] is None


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


# ---------------------------------------------------------------------------
# Broker identity endpoint + canonical start identity (adobepy #91)
# ---------------------------------------------------------------------------

_BROKER_WIRE_IDENTITY = {
    "pid": 2424,
    "runtimeVersion": "0.12.0",
    "executablePath": "C:/adobepy/adobepy.exe",
    "processStartIdentity": "windows-filetime:133700000000000000",
    "instanceId": "adobepy-test-instance",
}

_ATTESTATION_WIRE = {
    "identityVersion": 1,
    "broker": {
        "pid": 2424,
        "processStartIdentity": "windows-filetime:133700000000000000",
        "executablePath": "C:/adobepy/adobepy.exe",
        "runtimeVersion": "0.12.0",
        "instanceId": "76db1078-74c9-45c1-87e1-e8258649815e",
    },
    "host": {
        "pid": 4242,
        "processStartIdentity": "windows-filetime:133700000000000100",
        "executablePath": "C:/Adobe/Photoshop.exe",
        "hostVersion": "26.0",
        "profileId": "profile-production",
    },
    "bridge": {
        "target": "default",
        "bridgeKind": "uxp",
        "bridgeVersion": "0.12.0",
        "connectedAtEpochMs": 1720000000000,
        "instanceId": "9d31eb71-26cb-4c87-8b5a-4cadcc8e2f99",
        "installedPluginRoot": "C:/UXP/External/com.adobepy.bridge.photoshop",
        "moduleOrigin": "C:/UXP/External/com.adobepy.bridge.photoshop/dist/main.js",
    },
}

_EXPECTED_IDENTITY = {
    "host": "photoshop",
    "host_pid": 4242,
    "process_start_identity": "windows-filetime:133700000000000100",
    "process_executable": "C:/Adobe/Photoshop.exe",
    "host_version": "26.0",
    "profile_id": "profile-production",
    "target": "default",
    "bridge_kind": "uxp",
    "bridge_version": "0.12.0",
    "instance_id": "9d31eb71-26cb-4c87-8b5a-4cadcc8e2f99",
    "plugin_root": "C:/UXP/External/com.adobepy.bridge.photoshop",
    "plugin_module_origin": "C:/UXP/External/com.adobepy.bridge.photoshop/dist/main.js",
    "connected_at_epoch_ms": 1720000000000,
    "broker_url": "http://127.0.0.1:47391",
}


def test_broker_probe_fetches_and_maps_the_broker_identity(monkeypatch) -> None:
    monkeypatch.setenv("ADOBEPY_TOKEN", "broker-secret")
    seen = []

    def fake_request(request, _timeout):
        url = request.full_url
        seen.append((url, dict(request.header_items())))
        if url.endswith("/health"):
            return {"status": "ok", "protocol": "jsonrpc-2.0", "sessions": 1}, None
        if url.endswith("/v1/capabilities"):
            return [{"target": "default", "capabilities": {"host": "photoshop", "bridgeKind": "uxp"}}], None
        if url.endswith("/v1/broker-identity"):
            return dict(_BROKER_WIRE_IDENTITY), None
        return None, "http_error"

    monkeypatch.setattr(runtime_probe, "_request_json", fake_request)

    result = runtime_probe.probe_broker("http://127.0.0.1:47391", timeout=0.1)

    assert result["ok"] is True
    # camelCase wire identity mapped to the adapter's snake_case shape.
    assert result["identity"] == {
        "pid": 2424,
        "version": "0.12.0",
        "executable": "C:/adobepy/adobepy.exe",
        "process_start_identity": "windows-filetime:133700000000000000",
        "instance_id": "adobepy-test-instance",
    }
    identity_calls = [headers for url, headers in seen if url.endswith("/v1/broker-identity")]
    assert identity_calls
    assert any(value == "broker-secret" for value in identity_calls[0].values())


def test_broker_probe_identity_failure_is_non_fatal_to_liveness(monkeypatch) -> None:
    def fake_request(request, _timeout):
        url = request.full_url
        if url.endswith("/health"):
            return {"status": "ok", "protocol": "jsonrpc-2.0", "sessions": 0}, None
        if url.endswith("/v1/capabilities"):
            return [], None
        if url.endswith("/v1/broker-identity"):
            return None, "unauthorized"
        return None, "http_error"

    monkeypatch.setattr(runtime_probe, "_request_json", fake_request)

    result = runtime_probe.probe_broker("http://127.0.0.1:47391", timeout=0.1)

    # A pre-session watchdog only reads ok/sessions; identity absence must not
    # flip liveness, but verify later fails closed with invalid_identity.
    assert result["ok"] is True
    assert result["sessions"] == 0
    assert result["identity"] is None


def test_broker_probe_drops_a_partial_broker_identity_payload(monkeypatch) -> None:
    def fake_request(request, _timeout):
        url = request.full_url
        if url.endswith("/health"):
            return {"status": "ok", "protocol": "jsonrpc-2.0", "sessions": 0}, None
        if url.endswith("/v1/capabilities"):
            return [], None
        if url.endswith("/v1/broker-identity"):
            return {"pid": 2424, "runtimeVersion": "0.12.0"}, None
        return None, "http_error"

    monkeypatch.setattr(runtime_probe, "_request_json", fake_request)

    result = runtime_probe.probe_broker("http://127.0.0.1:47391", timeout=0.1)

    assert result["ok"] is True
    assert result["identity"] is None


def test_runtime_identity_mapping_flattens_the_sdk_attestation() -> None:
    from adobe.core import runtime_identity

    # Runtime identity is a required dependency contract, never an optional test.
    attestation = runtime_identity.RuntimeIdentityAttestation.from_broker(_ATTESTATION_WIRE)

    mapping = runtime_probe._runtime_identity_to_mapping(attestation, "http://127.0.0.1:47391")

    assert mapping == _EXPECTED_IDENTITY


def test_runtime_identity_mapping_accepts_a_plain_wire_mapping() -> None:
    mapping = runtime_probe._runtime_identity_to_mapping(_ATTESTATION_WIRE, "http://127.0.0.1:47391")

    assert mapping == _EXPECTED_IDENTITY


def test_runtime_identity_mapping_rejects_a_missing_sub_identity() -> None:
    assert runtime_probe._runtime_identity_to_mapping(None, "http://127.0.0.1:47391") is None
    assert runtime_probe._runtime_identity_to_mapping({"host": {}}, "http://127.0.0.1:47391") is None


def test_identity_field_prefers_attribute_then_wire_keys() -> None:
    assert runtime_probe._identity_field(None, "pid", "pid") is None

    @dataclass(frozen=True)
    class _Named:
        process_start_identity: str

    attribute = runtime_probe._identity_field(_Named("attr"), "process_start_identity", "processStartIdentity")
    camel = runtime_probe._identity_field(
        {"processStartIdentity": "camel"}, "process_start_identity", "processStartIdentity"
    )
    snake = runtime_probe._identity_field(
        {"process_start_identity": "snake"}, "process_start_identity", "processStartIdentity"
    )
    missing = runtime_probe._identity_field({}, "process_start_identity", "processStartIdentity")

    assert attribute == "attr"
    assert camel == "camel"
    assert snake == "snake"
    assert missing is None


@dataclass(frozen=True)
class _FakeHostIdentity:
    pid: int
    process_start_identity: str
    executable_path: str
    host_version: str
    profile_id: str


@dataclass(frozen=True)
class _FakeBridgeIdentity:
    target: str
    bridge_kind: str
    bridge_version: str
    connected_at_epoch_ms: int
    instance_id: str
    installed_plugin_root: str
    module_origin: str


@dataclass(frozen=True)
class _FakeAttestation:
    host: _FakeHostIdentity
    bridge: _FakeBridgeIdentity


def _fake_attestation() -> _FakeAttestation:
    host_wire = _ATTESTATION_WIRE["host"]
    bridge_wire = _ATTESTATION_WIRE["bridge"]
    return _FakeAttestation(
        host=_FakeHostIdentity(
            pid=host_wire["pid"],
            process_start_identity=host_wire["processStartIdentity"],
            executable_path=host_wire["executablePath"],
            host_version=host_wire["hostVersion"],
            profile_id=host_wire["profileId"],
        ),
        bridge=_FakeBridgeIdentity(
            target=bridge_wire["target"],
            bridge_kind=bridge_wire["bridgeKind"],
            bridge_version=bridge_wire["bridgeVersion"],
            connected_at_epoch_ms=bridge_wire["connectedAtEpochMs"],
            instance_id=bridge_wire["instanceId"],
            installed_plugin_root=bridge_wire["installedPluginRoot"],
            module_origin=bridge_wire["moduleOrigin"],
        ),
    )


def test_photoshop_probe_flattens_a_frozen_attestation_dataclass(monkeypatch) -> None:
    class FakePhotoshop:
        def __init__(self, **_kwargs) -> None:
            pass

        @property
        def version(self) -> str:
            return "26.0"

        def runtime_identity(self):
            return _fake_attestation()

    _install_module(monkeypatch, "adobe.photoshop", Photoshop=FakePhotoshop)

    result = runtime_probe.probe_photoshop("http://127.0.0.1:47391", timeout=0.1)

    assert result["ok"] is True
    assert result["identity"] == _EXPECTED_IDENTITY


def test_macos_process_start_identity_uses_proc_pidinfo(monkeypatch) -> None:
    calls = {}

    def fake_proc_pidinfo(pid, flavor, arg, buffer_arg, size):
        calls["pid"] = pid
        calls["flavor"] = flavor
        calls["size"] = size
        info = buffer_arg._obj
        info.start_seconds = 1_720_000_000
        info.start_microseconds = 12345
        return size

    class FakeLibproc:
        def __init__(self, path=None, *_args, **_kwargs) -> None:
            calls["path"] = path
            self.proc_pidinfo = fake_proc_pidinfo

    monkeypatch.setattr(install_verification.sys, "platform", "darwin")
    monkeypatch.setattr(ctypes, "CDLL", FakeLibproc)

    result = install_verification._process_start_identity(4242)

    # Canonical macOS token: macos:{tvsec}:{tvusec:06}, byte-identical to the broker.
    assert result == "macos:1720000000:012345"
    assert calls["path"] == "/usr/lib/libproc.dylib"
    assert calls["flavor"] == 3  # PROC_PIDTBSDINFO
    assert calls["size"] == 136  # sizeof(struct proc_bsdinfo)


def test_macos_process_start_identity_fails_closed_without_start_time(monkeypatch) -> None:
    def zero_proc_pidinfo(_pid, _flavor, _arg, buffer_arg, size):
        buffer_arg._obj.start_seconds = 0
        return size

    class FakeLibproc:
        def __init__(self, *_args, **_kwargs) -> None:
            self.proc_pidinfo = zero_proc_pidinfo

    monkeypatch.setattr(install_verification.sys, "platform", "darwin")
    monkeypatch.setattr(ctypes, "CDLL", FakeLibproc)

    assert install_verification._process_start_identity(4242) is None


def test_macos_process_start_identity_fails_closed_when_libproc_missing(monkeypatch) -> None:
    def raise_cdll(*_args, **_kwargs):
        raise OSError("libproc unavailable")

    monkeypatch.setattr(install_verification.sys, "platform", "darwin")
    monkeypatch.setattr(ctypes, "CDLL", raise_cdll)

    assert install_verification._process_start_identity(4242) is None
