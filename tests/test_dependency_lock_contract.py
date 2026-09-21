from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci.check_uv_lock import validate
from scripts.ci.check_uv_lock_freshness import align_root_version

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.8-3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _toml(relative: str):
    return tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_production_metadata_pins_the_reviewed_adobepy_runtime() -> None:
    dependencies = _toml("pyproject.toml")["project"]["dependencies"]

    assert dependencies.count("adobepy==0.6.2") == 1
    assert dependencies.count("dcc-mcp-core>=0.20.14,<0.21.0") == 1
    assert not any(dependency.startswith("adobepy>") for dependency in dependencies)


def test_checked_lock_has_one_current_root_and_reviewed_runtime() -> None:
    packages = _toml("uv.lock")["package"]
    roots = [package for package in packages if package.get("source") == {"editable": "."}]
    adobepy = [package for package in packages if package.get("name") == "adobepy"]
    core = [package for package in packages if package.get("name") == "dcc-mcp-core"]

    assert len(roots) == 1
    assert roots[0]["name"] == "dcc-mcp-photoshop"
    # The root version is a snapshot of the workspace version at lock time, not a contract:
    # release-please bumps project.version without re-resolving uv.lock.
    assert re.fullmatch(r"\d+\.\d+\.\d+", roots[0]["version"])
    assert [package["version"] for package in adobepy] == ["0.6.2"]
    assert len(core) == 1
    assert (0, 20, 14) <= tuple(int(part) for part in core[0]["version"].split(".")) < (0, 21, 0)
    assert {item["name"]: item.get("specifier") for item in roots[0]["metadata"]["requires-dist"]}[
        "adobepy"
    ] == "==0.6.2"


def test_lock_checker_accepts_the_checked_in_metadata() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/ci/check_uv_lock.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _copy_lock_inputs(destination: Path) -> None:
    for relative in ("pyproject.toml", "uv.lock", ".release-please-manifest.json"):
        shutil.copy2(ROOT / relative, destination / relative)


def _bump_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _simulate_release_please_bump(root: Path) -> str:
    """Reproduce a release-please bump: pyproject.toml + manifest move, uv.lock never does."""
    manifest_path = root / ".release-please-manifest.json"
    current = json.loads(manifest_path.read_text(encoding="utf-8"))["."]
    bumped = _bump_patch(current)

    pyproject_path = root / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    bumped_text, count = re.subn(
        r'(?m)^version = "' + re.escape(current) + r'"$',
        f'version = "{bumped}"',
        pyproject_text,
    )
    assert count == 1, f"expected exactly one project version line at {current}"
    pyproject_path.write_text(bumped_text, encoding="utf-8")
    manifest_path.write_text(json.dumps({".": bumped}, indent=2) + "\n", encoding="utf-8")
    return bumped


def test_lock_checker_ignores_release_driven_root_version_drift(tmp_path: Path) -> None:
    """Every release-please PR bumps pyproject.toml without re-locking; that must stay green."""
    _copy_lock_inputs(tmp_path)
    bumped = _simulate_release_please_bump(tmp_path)

    validate(tmp_path)

    packages = tomllib.loads((tmp_path / "uv.lock").read_text(encoding="utf-8"))["package"]
    root = next(package for package in packages if package.get("source") == {"editable": "."})
    assert root["version"] != bumped, "the fixture must leave the lock one bump behind"


def test_lock_freshness_aligns_only_the_root_version() -> None:
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    aligned = align_root_version(lock, "9.9.9")

    assert aligned.count('version = "9.9.9"') == 1
    assert 'name = "dcc-mcp-photoshop"\nversion = "9.9.9"' in aligned

    with pytest.raises(ValueError, match="exactly one dcc-mcp-photoshop root entry"):
        align_root_version('name = "other"\nversion = "0.1.0"\n', "9.9.9")


def test_lock_freshness_check_delegates_to_uv_lock_check() -> None:
    script = (ROOT / "scripts" / "ci" / "check_uv_lock_freshness.py").read_text(encoding="utf-8")

    assert '"-m", "uv", "lock", "--check"' in script


def test_lock_checker_rejects_a_shadow_editable_root(tmp_path: Path) -> None:
    _copy_lock_inputs(tmp_path)
    lock_path = tmp_path / "uv.lock"
    lock = lock_path.read_text(encoding="utf-8")
    lock += '\n[[package]]\nname = "shadow-root"\nversion = "0.1.38"\nsource = { editable = "." }\n'
    lock_path.write_text(lock, encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one source.editable"):
        validate(tmp_path)


def test_lock_checker_rejects_dependency_metadata_drift(tmp_path: Path) -> None:
    _copy_lock_inputs(tmp_path)
    lock_path = tmp_path / "uv.lock"
    lock = lock_path.read_text(encoding="utf-8").replace(
        '{ name = "adobepy", specifier = "==0.6.2" }',
        '{ name = "adobepy", specifier = ">=0.1.0" }',
        1,
    )
    lock_path.write_text(lock, encoding="utf-8")

    with pytest.raises(ValueError, match="root metadata must require adobepy"):
        validate(tmp_path)


def test_lock_checker_rejects_a_manifest_directory(tmp_path: Path) -> None:
    _copy_lock_inputs(tmp_path)
    manifest_path = tmp_path / ".release-please-manifest.json"
    manifest_path.unlink()
    manifest_path.mkdir()

    with pytest.raises(ValueError, match="release manifest must be a non-symlink regular file"):
        validate(tmp_path)


def test_lock_checker_rejects_a_same_bytes_manifest_symlink(tmp_path: Path) -> None:
    _copy_lock_inputs(tmp_path)
    manifest_path = tmp_path / ".release-please-manifest.json"
    manifest_target = tmp_path / "manifest-target.json"
    shutil.copy2(manifest_path, manifest_target)
    manifest_path.unlink()
    try:
        manifest_path.symlink_to(manifest_target.name)
    except OSError as exc:  # pragma: no cover - local Windows policy may deny symlink creation
        pytest.skip(f"file symlinks are unavailable: {exc.__class__.__name__}")

    assert manifest_path.read_bytes() == manifest_target.read_bytes()
    with pytest.raises(ValueError, match="release manifest must be a non-symlink regular file"):
        validate(tmp_path)


def test_ci_resolves_core_floor_and_latest_and_checks_the_lock() -> None:
    document = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    jobs = document["jobs"]
    dependency = jobs["dependency-contract"]
    lock = jobs["lock-contract"]
    dependency_runs = "\n".join(str(step.get("run", "")) for step in dependency["steps"])
    lock_runs = "\n".join(str(step.get("run", "")) for step in lock["steps"])

    assert dependency["strategy"]["matrix"]["mode"] == ["floor", "latest"]
    assert 'python -m pip install . "dcc-mcp-core==0.20.14"' in dependency_runs
    assert "python -m pip install ." in dependency_runs
    assert "python -m pip check" in dependency_runs
    assert "python scripts/ci/check_installed_dependencies.py" in dependency_runs
    assert "python scripts/ci/check_uv_lock.py" in lock_runs
    assert "python scripts/ci/check_uv_lock_freshness.py" in lock_runs
    assert {"dependency-contract", "lock-contract"} <= set(jobs["ci-gate"]["needs"])
