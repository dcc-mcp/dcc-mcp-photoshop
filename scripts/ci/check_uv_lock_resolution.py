"""Check that uv.lock still resolves the committed dependency metadata.

`uv lock --check` treats the editable root's own `version` as part of the lock,
so it reports "needs to be updated" whenever `project.version` moves. That is
exactly what release-please does on every release PR: it bumps
`pyproject.toml`, `src/dcc_mcp_photoshop/__version__.py`,
`.release-please-manifest.json` and the changelog, but never regenerates
`uv.lock`. The root version is pure metadata -- it is not an input to
resolution -- so a release PR legitimately carries a one-field drift there.

This script keeps `uv lock --check` meaningful across those releases: it copies
the project to a scratch directory, normalises *only* the editable root version
to match `pyproject.toml`, and then lets uv verify that every resolved
dependency still matches. Real drift -- a changed pin, a new dependency, an
edited `requires-python` -- still fails, because none of those are normalised.

A normalisation that cannot find the field it expects is a hard failure rather
than a silent pass, so a future uv format change cannot quietly downgrade this
check into a no-op.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.8-3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
ROOT_NAME = "dcc-mcp-photoshop"

# Directories that are large, regenerable, or irrelevant to resolution.
SCRATCH_EXCLUSIONS = (
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "*.egg-info",
    "build",
    "dist",
    "node_modules",
    "venv",
)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _project_version(root: Path) -> str:
    project = _mapping(tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("project"), "project")
    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("project.version must be a non-empty string")
    return version


def _editable_root_version(lock_text: str) -> tuple[str, str]:
    """Return the (name, version) of the single editable root in a uv.lock."""
    packages = _list(tomllib.loads(lock_text).get("package"), "uv.lock package")
    roots = [
        package for package in packages if _mapping(package.get("source"), "package.source").get("editable") == "."
    ]
    if len(roots) != 1:
        raise ValueError(f"uv.lock must contain exactly one editable root, found {len(roots)}")
    name = roots[0].get("name")
    version = roots[0].get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError("editable root must declare string name and version")
    return name, version


def normalise_root_version(lock_text: str, version: str) -> str:
    """Rewrite the editable root's version to ``version``, leaving everything else byte-identical."""
    name, locked = _editable_root_version(lock_text)
    if name != ROOT_NAME:
        raise ValueError(f"editable root must be {ROOT_NAME!r}, found {name!r}")
    if locked == version:
        return lock_text

    pattern = re.compile(
        r'(^\[\[package\]\]\nname = "' + re.escape(name) + r'"\nversion = ")' + re.escape(locked) + r'(")',
        re.MULTILINE,
    )
    normalised, replacements = pattern.subn(rf"\g<1>{version}\g<2>", lock_text)
    if replacements != 1:
        raise ValueError(
            f"could not rewrite the {ROOT_NAME!r} root version in uv.lock "
            f"({replacements} matches); the uv.lock layout changed and this normalisation must be updated"
        )
    _editable_root_version(normalised)  # fail closed if the rewrite produced invalid TOML
    return normalised


def check(root: Path) -> tuple[int, str]:
    version = _project_version(root)
    lock_text = (root / "uv.lock").read_text(encoding="utf-8")
    normalised = normalise_root_version(lock_text, version)

    with tempfile.TemporaryDirectory(prefix="uv-lock-resolution-") as temporary:
        scratch = Path(temporary) / "project"
        shutil.copytree(root, scratch, ignore=shutil.ignore_patterns(*SCRATCH_EXCLUSIONS))
        if normalised != lock_text:
            # Write bytes so the scratch lock keeps LF endings on every platform.
            (scratch / "uv.lock").write_bytes(normalised.encode("utf-8"))

        completed = subprocess.run(
            [sys.executable, "-m", "uv", "lock", "--check", "--project", str(scratch)],
            cwd=str(scratch),
            capture_output=True,
            text=True,
            check=False,
        )

    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def main() -> int:
    if importlib.util.find_spec("uv") is None:
        print("uv lock resolution check failed: uv is not importable (pip install uv)", file=sys.stderr)
        return 1

    try:
        returncode, output = check(ROOT)
    except ValueError as exc:
        print(f"uv lock resolution check failed: {exc}", file=sys.stderr)
        return 1

    if returncode != 0:
        print("uv.lock does not match pyproject.toml:", file=sys.stderr)
        print(output, file=sys.stderr)
        print("Run `uv lock` and commit the result.", file=sys.stderr)
        return 1

    print("uv lock resolution matches pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
