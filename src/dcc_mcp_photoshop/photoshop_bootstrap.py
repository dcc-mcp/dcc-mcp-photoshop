"""adobepy 0.12.0 bounded Photoshop UXP bootstrap integration.

``adobepy`` 0.12.0 exposes a two-step, identity-bound bootstrap handshake on
the broker::

    BrokerClient.bootstrap_photoshop_uxp(request)      -> PhotoshopBootstrapResult
    BrokerClient.verify_photoshop_bootstrap(receipt)   -> PhotoshopBootstrapResult

Both steps are bound to *exact* host/plugin identity facts via
``require_request`` / ``require_continuation``. A successful handshake is what
establishes a single, trusted UXP session — the prerequisite for real RPC and
any native end-to-end color-lookup validation.

This module is the thin adapter that turns a plain identity ``facts`` mapping
into a validated :class:`PhotoshopBootstrapRequest`, drives the two-step
handshake over an injected ``BrokerClient`` (so it is fully offline-testable),
and returns a small, redacted result. It deliberately does NOT invent identity
facts: the host executable path/hash, plugin module hashes, profile id,
``ADOBEPY_TOKEN`` and the receipt-backed bridge must all come from a real,
authorized installation. Nothing here bypasses broker identity, fabricates a
session, or claims native acceptance the broker has not granted.
"""

from __future__ import annotations

from typing import Any, Mapping

from adobe.core import (
    BrokerClient,
    PhotoshopBootstrapRequest,
    PhotoshopBootstrapResult,
)
from adobe.core.errors import AdobePythonError

from dcc_mcp_photoshop.bootstrap_diagnostics import redact_bootstrap_message

STATUS_READY = "ready"
STATUS_BLOCKED = "blocked"
STATUS_IDENTITY_MISMATCH = "identity_mismatch"
STATUS_INSTANCE_MISMATCH = "instance_mismatch"
STATUS_INVALID_FACTS = "invalid_facts"

_BOOTSTRAP_PATH = "/v1/photoshop/bootstrap"
_VERIFY_PATH = "/v1/photoshop/bootstrap/verify"


def build_bootstrap_request(facts: Mapping[str, Any]) -> PhotoshopBootstrapRequest:
    """Validate identity ``facts`` and build a ``PhotoshopBootstrapRequest``.

    Delegates all validation to ``PhotoshopBootstrapRequest.from_mapping`` so
    the adapter cannot drift from the SDK's exact-runtime-identity contract.
    Raises ``ValueError`` for malformed facts.
    """
    return PhotoshopBootstrapRequest.from_mapping(dict(facts))


def _redacted_summary(result: PhotoshopBootstrapResult) -> dict[str, Any]:
    """Return only non-sensitive identity fields from a verified result."""
    return {
        "status": STATUS_READY,
        "host_version": result.host.host_version,
        "profile_id": result.host.profile_id,
        "bridge_version": result.plugin.bridge_version,
        "executable_sha256": result.host.executable_sha256,
        "module_sha256": result.plugin.module_sha256,
        "continuation_path": result.continuation.path,
    }


def _failure(reason: str, message: str) -> dict[str, Any]:
    return {
        "status": STATUS_BLOCKED,
        "reason": reason,
        "message": redact_bootstrap_message(message),
    }


def _runtime_binding(result: PhotoshopBootstrapResult) -> tuple[Any, ...]:
    """Return the live-instance binding fields of a bootstrap/verify result.

    ``require_request`` / ``require_continuation`` bind each result to the
    request and the receipt, but neither compares the two results' runtime
    bindings. A broker/host/plugin process can restart between the bootstrap
    and verify calls; if the second result describes a different live instance
    (PIDs, process-start identities, instance ids, or a different identity
    fingerprint), returning ``ready`` would attest to the wrong runtime. These
    fields are the exact-instance facts the SDK exposes for that comparison.
    """
    return (
        result.identity_fingerprint,
        result.broker,
        result.host,
        result.plugin,
    )


def run_bounded_bootstrap(
    client: BrokerClient,
    request: PhotoshopBootstrapRequest,
) -> dict[str, Any]:
    """Drive the two-step bounded bootstrap over an injected ``client``.

    Enforces exact-request and exact-continuation identity binding (in addition
    to the checks performed inside the real ``BrokerClient``), then returns a
    redacted summary. Broker and identity failures return a structured result
    instead of raising, so callers can record an honest blocker.
    """
    try:
        bootstrap_result = client.bootstrap_photoshop_uxp(request)
        # Re-assert exact-request binding even for a client that skipped it.
        bootstrap_result.require_request(request)
        continuation = bootstrap_result.continuation
        verify_result = client.verify_photoshop_bootstrap(continuation)
        verify_result.require_request(request)
        verify_result.require_continuation(continuation)
    except AdobePythonError as exc:
        return _failure(type(exc).__name__, str(exc))
    except ValueError as exc:
        return {
            "status": STATUS_IDENTITY_MISMATCH,
            "reason": "identity_binding_rejected",
            "message": redact_bootstrap_message(str(exc)),
        }
    # require_request / require_continuation bind each result to the request
    # and the receipt independently, but neither compares the two results to
    # each other. Reject a verify result that describes a different live
    # runtime instance than bootstrap (broker/host/plugin restart between the
    # two calls), so we never attest to the wrong runtime.
    if _runtime_binding(bootstrap_result) != _runtime_binding(verify_result):
        return {
            "status": STATUS_INSTANCE_MISMATCH,
            "reason": "runtime_instance_changed",
            "message": "bootstrap and verification are bound to different runtime instances",
        }
    return _redacted_summary(verify_result)


def bootstrap_from_facts(
    facts: Mapping[str, Any],
    *,
    client: BrokerClient | None = None,
) -> dict[str, Any]:
    """Build a request from ``facts`` and run the bounded bootstrap.

    When ``client`` is omitted a real ``BrokerClient`` is constructed; it reads
    ``ADOBEPY_BROKER_URL`` / ``ADOBEPY_TOKEN`` / ``ADOBEPY_TARGET`` from the
    environment. Passing an injected client is the offline test seam and never
    performs network I/O.
    """
    try:
        request = build_bootstrap_request(facts)
    except (ValueError, TypeError) as exc:
        return {
            "status": STATUS_INVALID_FACTS,
            "reason": "invalid_identity_facts",
            "message": redact_bootstrap_message(str(exc)),
        }
    active_client = client if client is not None else BrokerClient()
    return run_bounded_bootstrap(active_client, request)


def describe_bootstrap_contract() -> dict[str, Any]:
    """Describe the bounded bootstrap capability without exposing any secret.

    Useful for diagnostics / install reports that need to state which broker
    endpoints the adapter can drive, without embedding a token, a local path,
    or a private identity value.
    """
    return {
        "sdk": "adobepy==0.12.0",
        "request_type": "PhotoshopBootstrapRequest",
        "bootstrap_path": _BOOTSTRAP_PATH,
        "verify_path": _VERIFY_PATH,
        "identity_binding": [
            "require_request",
            "require_continuation",
            "same_runtime_instance",
        ],
        "requires": [
            "official adobepy Windows broker CLI",
            "ADOBEPY_TOKEN",
            "receipt-backed UXP bridge",
            "exact host + plugin identity facts",
        ],
    }
