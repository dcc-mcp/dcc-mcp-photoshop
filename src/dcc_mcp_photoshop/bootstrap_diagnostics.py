"""Bounded, redacted bootstrap diagnostics for the Photoshop adapter."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def _diagnostic_path() -> Path:
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    root = Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
    return root / "bootstrap-errors.json"


def redact_bootstrap_message(message: str) -> str:
    """Remove configured secrets and URL userinfo from a diagnostic message."""
    redacted = str(message)
    for name in ("ADOBEPY_TOKEN", "ADOBE_TOKEN"):
        secret = os.environ.get(name, "")
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return re.sub(r"(https?://)[^/@\s]+@", r"\1<redacted>@", redacted)


def capture_bootstrap_error(stage: str, message: str) -> str:
    """Persist one bounded failure and return its redacted message."""
    safe_message = redact_bootstrap_message(message)
    path = _diagnostic_path()
    errors: list[dict[str, str]] = []
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(current.get("errors"), list):
            errors = [item for item in current["errors"] if isinstance(item, dict)][-19:]
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    errors.append(
        {
            "stage": str(stage),
            "message": safe_message,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"errors": errors}, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        pass
    return safe_message
