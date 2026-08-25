from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci.check_uv_lock import validate

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
    assert dependencies.count("dcc-mcp-core>=0.20.14,<1.0.0") == 1
    assert not any(dependency.startswith("adobepy>") for dependency in dependencies)


def test_checked_lock_has_one_current_root_and_reviewed_runtime() -> None:
    project = _toml("pyproject.toml")["project"]
    packages = _toml("uv.lock")["package"]
    roots = [package for package in packages if package.get("source") == {"editable": "."}]
    adobepy = [package for package in packages if package.get("name") == "adobepy"]
    core = [package for package in packages if package.get("name") == "dcc-mcp-core"]

    assert len(roots) == 1
    assert (roots[0]["name"], roots[0]["version"]) == ("dcc-mcp-photoshop", project["version"])
    assert [package["version"] for package in adobepy] == ["0.6.2"]
    assert len(core) == 1
    assert (0, 20, 14) <= tuple(int(part) for part in core[0]["version"].split(".")) < (1, 0, 0)
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
    assert "python -m uv lock --check" in lock_runs
    assert {"dependency-contract", "lock-contract"} <= set(jobs["ci-gate"]["needs"])
