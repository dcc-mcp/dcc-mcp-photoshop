"""Regression tests for the adobepy 0.12.0 bounded bootstrap integration.

OFFLINE ONLY. These tests use an injected fake ``BrokerClient`` that returns
real ``PhotoshopBootstrapResult`` objects built from valid synthetic wire data.
They verify request validation, the two-step handshake, exact-request and
exact-continuation identity binding, redaction, and structured failure paths.
They do NOT open a network connection, contact a real broker, or establish a
native UXP session.
"""

from __future__ import annotations

from typing import Any

import pytest
from adobe.core import PhotoshopBootstrapRequest, PhotoshopBootstrapResult
from adobe.core.errors import BrokerConnectionError

from dcc_mcp_photoshop import photoshop_bootstrap as pb

_SHA = "a" * 64
_UUID = "11111111-1111-4111-8111-111111111111"
_ROOT = "/opt/bridge"


def _facts(**overrides: Any) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "bootstrapVersion": 1,
        "target": "photoshop-uxp",
        "timeoutMs": 5000,
        "host": {
            "executablePath": "/opt/Adobe/Photoshop/Photoshop",
            "executableBytes": 12345678,
            "executableSha256": _SHA,
            "hostVersion": "26.0",
            "profileId": "default",
        },
        "plugin": {
            "installedPluginRoot": _ROOT,
            "moduleOrigin": _ROOT + "/dist/main.js",
            "bridgeVersion": "0.12.0",
            "manifestBytes": 100,
            "manifestSha256": _SHA,
            "indexBytes": 200,
            "indexSha256": _SHA,
            "moduleBytes": 300,
            "moduleSha256": _SHA,
        },
    }
    facts.update(overrides)
    return facts


def _wire(host_version: str = "26.0", status: str = "ready") -> dict[str, Any]:
    return {
        "bootstrapVersion": 1,
        "status": status,
        "identityFingerprint": _SHA,
        "broker": {
            "pid": 1001,
            "processStartIdentity": "boot:1001",
            "runtimeVersion": "1.2.3",
            "instanceId": _UUID,
            "executableSha256": _SHA,
        },
        "host": {
            "pid": 2002,
            "processStartIdentity": "boot:2002",
            "hostVersion": host_version,
            "profileId": "default",
            "executableSha256": _SHA,
        },
        "plugin": {
            "instanceId": _UUID,
            "bridgeVersion": "0.12.0",
            "moduleSha256": _SHA,
        },
        "continuation": {
            "method": "POST",
            "path": "/v1/photoshop/bootstrap/verify",
            "receiptId": _UUID,
            "timeoutMs": 5000,
        },
    }


class _FakeBrokerClient:
    """Minimal BrokerClient stand-in with independent bootstrap/verify wires."""

    def __init__(
        self,
        *,
        bootstrap_wire: dict[str, Any] | None = None,
        verify_wire: dict[str, Any] | None = None,
        bootstrap_error: Exception | None = None,
    ) -> None:
        self.bootstrap_wire = bootstrap_wire or _wire()
        self.verify_wire = verify_wire or _wire()
        self.bootstrap_error = bootstrap_error
        self.bootstrap_calls: list[PhotoshopBootstrapRequest] = []
        self.verify_calls: list[Any] = []

    def bootstrap_photoshop_uxp(self, request: PhotoshopBootstrapRequest) -> PhotoshopBootstrapResult:
        self.bootstrap_calls.append(request)
        if self.bootstrap_error:
            raise self.bootstrap_error
        return PhotoshopBootstrapResult.from_broker(self.bootstrap_wire)

    def verify_photoshop_bootstrap(self, continuation: Any) -> PhotoshopBootstrapResult:
        self.verify_calls.append(continuation)
        return PhotoshopBootstrapResult.from_broker(self.verify_wire)


class TestBuildBootstrapRequest:
    def test_builds_valid_request_from_facts(self):
        request = pb.build_bootstrap_request(_facts())
        wire = request.to_wire()
        assert wire["bootstrapVersion"] == 1
        assert wire["host"]["hostVersion"] == "26.0"
        assert wire["plugin"]["moduleOrigin"] == _ROOT + "/dist/main.js"

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda f: f.pop("host"),
            lambda f: f["host"].update({"hostVersion": ""}),
            lambda f: f["plugin"].update({"moduleOrigin": "/elsewhere/main.js"}),
            lambda f: f.update({"bootstrapVersion": 2}),
            lambda f: f.update({"timeoutMs": 1}),
            lambda f: f["host"].update({"executableSha256": "not-a-hash"}),
        ],
    )
    def test_invalid_facts_are_rejected_by_sdk(self, mutate):
        facts = _facts()
        mutate(facts)
        with pytest.raises(ValueError):
            pb.build_bootstrap_request(facts)


class TestRunBoundedBootstrap:
    def test_happy_path_two_step_handshake(self):
        client = _FakeBrokerClient()
        request = pb.build_bootstrap_request(_facts())

        result = pb.run_bounded_bootstrap(client, request)

        assert result["status"] == pb.STATUS_READY
        assert result["host_version"] == "26.0"
        assert result["executable_sha256"] == _SHA
        assert result["continuation_path"] == "/v1/photoshop/bootstrap/verify"
        assert len(client.bootstrap_calls) == 1
        assert len(client.verify_calls) == 1

    def test_verify_receives_exact_bootstrap_continuation(self):
        client = _FakeBrokerClient()
        request = pb.build_bootstrap_request(_facts())

        pb.run_bounded_bootstrap(client, request)

        bootstrap_result = PhotoshopBootstrapResult.from_broker(client.bootstrap_wire)
        assert client.verify_calls[0] == bootstrap_result.continuation

    def test_broker_error_returns_structured_blocked(self):
        client = _FakeBrokerClient(bootstrap_error=BrokerConnectionError("broker unavailable"))
        request = pb.build_bootstrap_request(_facts())

        result = pb.run_bounded_bootstrap(client, request)

        assert result["status"] == pb.STATUS_BLOCKED
        assert result["reason"] == "BrokerConnectionError"
        assert "broker unavailable" in result["message"]
        assert client.verify_calls == []

    def test_identity_mismatch_is_rejected(self):
        # Broker result claims a different host version than the request.
        client = _FakeBrokerClient(bootstrap_wire=_wire(host_version="99.9"))
        request = pb.build_bootstrap_request(_facts())

        result = pb.run_bounded_bootstrap(client, request)

        assert result["status"] == pb.STATUS_IDENTITY_MISMATCH
        assert result["reason"] == "identity_binding_rejected"

    def test_secret_is_redacted_from_error_message(self, monkeypatch):
        monkeypatch.setenv("ADOBEPY_TOKEN", "super-secret-token-value")
        client = _FakeBrokerClient(bootstrap_error=BrokerConnectionError("auth failed for super-secret-token-value"))
        request = pb.build_bootstrap_request(_facts())

        result = pb.run_bounded_bootstrap(client, request)

        assert "super-secret-token-value" not in result["message"]
        assert "<redacted>" in result["message"]


class TestBootstrapFromFacts:
    def test_invalid_facts_short_circuit_without_client(self):
        result = pb.bootstrap_from_facts({"nonsense": True})

        assert result["status"] == pb.STATUS_INVALID_FACTS
        assert result["reason"] == "invalid_identity_facts"

    def test_injected_client_drives_full_handshake(self):
        client = _FakeBrokerClient()
        result = pb.bootstrap_from_facts(_facts(), client=client)

        assert result["status"] == pb.STATUS_READY
        assert len(client.bootstrap_calls) == 1


class TestDescribeContract:
    def test_contract_is_descriptive_and_secret_free(self):
        contract = pb.describe_bootstrap_contract()

        assert contract["sdk"] == "adobepy==0.12.0"
        assert contract["bootstrap_path"] == "/v1/photoshop/bootstrap"
        assert contract["verify_path"] == "/v1/photoshop/bootstrap/verify"
        assert "require_request" in contract["identity_binding"]
        assert "require_continuation" in contract["identity_binding"]
        assert "ADOBEPY_TOKEN" in contract["requires"]
