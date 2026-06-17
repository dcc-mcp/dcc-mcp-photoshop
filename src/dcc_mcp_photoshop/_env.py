"""Environment-variable resolution for ``PhotoshopMcpServer``.

Centralises every ``DCC_MCP_PHOTOSHOP_*`` env var used by the server so the
composition root in :mod:`dcc_mcp_photoshop.server` stays a thin orchestrator.

All helpers are pure functions: they read :data:`os.environ` and return
plain Python values; they never mutate global state.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Public env-var names ─────────────────────────────────────────────────────
ENV_METRICS = "DCC_MCP_PHOTOSHOP_METRICS"
ENV_JOB_STORAGE = "DCC_MCP_PHOTOSHOP_JOB_STORAGE"
ENV_JOB_RECOVERY = "DCC_MCP_PHOTOSHOP_JOB_RECOVERY"
ENV_STRICT_SKILL_SCAN = "DCC_MCP_PHOTOSHOP_STRICT_SKILL_SCAN"
ENV_ENABLE_GATEWAY_FAILOVER = "DCC_MCP_PHOTOSHOP_ENABLE_GATEWAY_FAILOVER"
ENV_READINESS_TIMEOUT_SECS = "DCC_MCP_PHOTOSHOP_READINESS_TIMEOUT_SECS"
#: Default SQLite filename inside the platform data directory.
DEFAULT_JOB_DB_FILENAME = "jobs.db"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def resolve_metrics_enabled(metrics_enabled: Optional[bool]) -> bool:
    """Resolve the Prometheus ``/metrics`` endpoint flag.

    Priority: explicit argument > ``DCC_MCP_PHOTOSHOP_METRICS=1`` > ``False``.
    """
    if metrics_enabled is not None:
        return bool(metrics_enabled)
    return os.environ.get(ENV_METRICS, "").strip() == "1"


def resolve_job_storage(job_storage_path: Optional[str]) -> Optional[str]:
    """Resolve the SQLite job-storage path.

    Returns ``None`` when callers should leave whatever path
    :class:`DccServerBase._init_job_persistence` selected.  Returns the
    empty string ``""`` when the caller passed ``""`` explicitly to
    request in-memory operation (no persistence).

    Priority order:

    1. Explicit ``job_storage_path`` argument (when not ``None``).  An
       empty string preserves the empty intent.
    2. ``DCC_MCP_PHOTOSHOP_JOB_STORAGE`` env var.
    3. ``<platform_data_dir>/dcc-mcp-photoshop/jobs.db`` (auto-created).
    """
    if job_storage_path is not None:
        if not str(job_storage_path).strip():
            return ""  # explicit "disable persistence"
        return job_storage_path

    env_val = os.environ.get(ENV_JOB_STORAGE)
    if env_val is not None:
        return env_val

    try:
        from dcc_mcp_core import get_data_dir  # noqa: PLC0415

        data_dir = Path(get_data_dir()) / "dcc-mcp-photoshop"
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / DEFAULT_JOB_DB_FILENAME)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not resolve default job storage path: %s", exc)
        return None


def resolve_job_recovery(job_recovery: Optional[str]) -> str:
    """Resolve the interrupted-job recovery policy.

    Returns either ``"drop"`` (default — discard interrupted jobs) or
    ``"requeue"`` (re-submit idempotent jobs on startup).  Any other
    value (including a malformed env var) collapses to ``"drop"`` so the
    server never starts in an undefined state.

    Priority: explicit argument > ``DCC_MCP_PHOTOSHOP_JOB_RECOVERY`` > ``"drop"``.
    """
    raw: Optional[str]
    if job_recovery is not None:
        raw = job_recovery
    else:
        raw = os.environ.get(ENV_JOB_RECOVERY, "drop")
    normalised = (raw or "drop").strip().lower()
    return normalised if normalised in ("drop", "requeue") else "drop"


def resolve_strict_skill_scan(strict: Optional[bool] = None) -> bool:
    """Resolve whether to run strict skill validation after discovery.

    Priority: explicit ``strict`` argument > ``DCC_MCP_PHOTOSHOP_STRICT_SKILL_SCAN=1``
    > ``False``.
    """
    if strict is not None:
        return bool(strict)
    return os.environ.get(ENV_STRICT_SKILL_SCAN, "").strip() == "1"


def resolve_enable_gateway_failover(
    enable_gateway_failover: Optional[bool],
    *,
    default: bool = True,
) -> bool:
    """Resolve gateway failover from constructor + optional env override.

    Priority: explicit ``enable_gateway_failover`` argument (when not ``None``)
    > ``DCC_MCP_PHOTOSHOP_ENABLE_GATEWAY_FAILOVER`` (when set) > ``default``.
    """
    if enable_gateway_failover is not None:
        return bool(enable_gateway_failover)
    raw = os.environ.get(ENV_ENABLE_GATEWAY_FAILOVER, "").strip()
    if raw:
        return _env_truthy(ENV_ENABLE_GATEWAY_FAILOVER)
    return bool(default)


def resolve_readiness_timeout_secs(
    readiness_timeout_secs: Optional[int] = None,
) -> Optional[int]:
    """Resolve ``DCC_MCP_PHOTOSHOP_READINESS_TIMEOUT_SECS`` into a positive integer.

    Priority: explicit argument > env var > ``None``.  ``None`` means
    "no Photoshop-side timeout — let the orchestrator decide".  Invalid
    values (non-integer, ``<= 0``) collapse to ``None`` and log a
    warning so a typo never kills startup.
    """
    if readiness_timeout_secs is not None:
        try:
            val = int(readiness_timeout_secs)
        except (TypeError, ValueError):
            return None
        return val if val > 0 else None

    raw = os.environ.get(ENV_READINESS_TIMEOUT_SECS)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        val = int(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid %s=%r (expected positive integer seconds)",
            ENV_READINESS_TIMEOUT_SECS,
            raw,
        )
        return None
    if val <= 0:
        logger.warning(
            "Ignoring non-positive %s=%r (expected positive integer seconds)",
            ENV_READINESS_TIMEOUT_SECS,
            raw,
        )
        return None
    return val
