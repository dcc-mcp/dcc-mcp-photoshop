"""Bounded, redacted bootstrap diagnostics for the Photoshop adapter."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_URL_SPAN = re.compile(
    r'"(?:https?|file|ftp|wss?)://[^"<>]*"|'
    r"'(?:https?|file|ftp|wss?)://[^'<>]*'|"
    r"(?:https?|file|ftp|wss?)://[^\s\"'<>]+",
    re.IGNORECASE,
)
_URL_USERINFO = re.compile(
    r"((?:https?|file|ftp|wss?)://)[^/@\s]+@",
    re.IGNORECASE,
)
_URL_TOKEN = re.compile(r"\x00DCC_URL_(\d+)\x00")
_QUOTED_POSIX_PATH = re.compile(r"""(["'])/(?!/)[^"'<>]+\1""")
_UNQUOTED_POSIX_PATH = re.compile(r'(?<![A-Za-z0-9])/(?!/)(?:[^/\s"\'<>](?:[^/"\'<>]*[^/\s"\'<>])?/)*[^\s/"\'<>]+/?')
_QUOTED_WINDOWS_PATH = re.compile(r"""(["'])(?:[A-Za-z]:[\\/]|\\\\)[^"'<>]+\1""")
_UNQUOTED_WINDOWS_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\)"
    r'(?:[^\\/\s"\'<>](?:[^\\/"\'<>]*[^\\/\s"\'<>])?[\\/])*'
    r'[^\s\\/"\'<>]+[\\/]?'
)


def _diagnostic_path() -> Path:
    configured = os.environ.get("DCC_MCP_PHOTOSHOP_INSTALL_STATE_DIR")
    root = Path(configured).expanduser() if configured else Path.home() / ".dcc-mcp" / "photoshop"
    return root / "bootstrap-errors.json"


def redact_bootstrap_message(message: str) -> str:
    """Remove configured secrets, URL userinfo, and local paths from diagnostics."""
    redacted = str(message)
    for name in ("ADOBEPY_TOKEN", "ADOBE_TOKEN"):
        secret = os.environ.get(name, "")
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    # Bootstrap errors are persisted and may be uploaded by diagnostics. Keep
    # machine-local paths out of that public surface while preserving the
    # stage/error text. Both native Windows and POSIX spellings are covered,
    # including foreign-platform paths received from a host subprocess.
    urls: list[str] = []

    def protect_url(match: re.Match[str]) -> str:
        urls.append(_URL_USERINFO.sub(r"\1<redacted>@", match.group(0)))
        return f"\x00DCC_URL_{len(urls) - 1}\x00"

    protected = _URL_SPAN.sub(protect_url, redacted)
    protected = _QUOTED_WINDOWS_PATH.sub("<redacted-path>", protected)
    protected = _UNQUOTED_WINDOWS_PATH.sub("<redacted-path>", protected)
    protected = _QUOTED_POSIX_PATH.sub("<redacted-path>", protected)
    protected = _UNQUOTED_POSIX_PATH.sub("<redacted-path>", protected)

    def restore_url(match: re.Match[str]) -> str:
        return urls[int(match.group(1))]

    return _URL_TOKEN.sub(restore_url, protected)


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
