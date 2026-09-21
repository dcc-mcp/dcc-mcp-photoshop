"""Verify the committed ``uv.lock`` is a fresh resolution of ``pyproject.toml``.

``uv.lock`` records the editable root's version as a snapshot taken the last time the
lock was resolved. Release Please bumps ``project.version`` in ``pyproject.toml``
without re-resolving the lock, so every release PR legitimately carries a root version
one bump behind — and ``uv lock --check`` reports that as "lockfile needs to be
updated" even though nothing a consumer depends on has drifted.

Aligning the recorded root version with ``project.version`` before delegating to
``uv lock --check`` keeps the gate sensitive to real drift (a dependency added,
removed or re-pinned in ``pyproject.toml`` without a re-lock) while letting release
automation through.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.8-3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[2]
ROOT_NAME = "dcc-mcp-photoshop"
ROOT_VERSION_PATTERN = re.compile(r'(?m)^name = "' + re.escape(ROOT_NAME) + r'"\nversion = "[^"\n]+"\n')


def align_root_version(lock_text: str, version: str) -> str:
    """Return ``lock_text`` with the editable root version set to ``version``."""
    replacement = f'name = "{ROOT_NAME}"\nversion = "{version}"\n'
    aligned, replacements = ROOT_VERSION_PATTERN.subn(replacement, lock_text)
    if replacements != 1:
        raise ValueError(f"expected exactly one {ROOT_NAME} root entry in uv.lock, found {replacements}")
    return aligned


def main() -> int:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    lock_path = ROOT / "uv.lock"
    committed = lock_path.read_text(encoding="utf-8")
    aligned = align_root_version(committed, version)

    try:
        if aligned != committed:
            lock_path.write_text(aligned, encoding="utf-8")
        return subprocess.run([sys.executable, "-m", "uv", "lock", "--check"], cwd=ROOT).returncode
    finally:
        if aligned != committed:
            lock_path.write_text(committed, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
