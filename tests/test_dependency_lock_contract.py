from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci.check_uv_lock import FINAL_VERSION, validate
from scripts.ci.check_uv_lock_resolution import ROOT_NAME, check, normalise_root_version

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.8-3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _toml(relative: str):
    return tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))


def _editable_root(lock_text: str):
    """Return the (name, version) of the single editable root in a uv.lock document."""
    packages = tomllib.loads(lock_text)["package"]
    roots = [package for package in packages if package.get("source") == {"editable": "."}]
    return roots[0]["name"], roots[0]["version"]


def _uv_is_importable() -> bool:
    import importlib.util

    return importlib.util.find_spec("uv") is not None


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
    # The root version is intentionally not compared against project.version: release-please
    # owns project.version and bumps it without regenerating uv.lock. See
    # test_release_version_bump_keeps_the_lock_contract_valid below.
    assert roots[0]["name"] == "dcc-mcp-photoshop"
    assert FINAL_VERSION.fullmatch(roots[0]["version"]) is not None
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


def test_lock_resolution_checker_accepts_the_checked_in_metadata() -> None:
    if shutil.which("uv") is None and not _uv_is_importable():
        pytest.skip("uv is not installed")

    returncode, output = check(ROOT)

    assert returncode == 0, output


def _copy_lock_inputs(destination: Path) -> None:
    for relative in ("pyproject.toml", "uv.lock", ".release-please-manifest.json"):
        shutil.copy2(ROOT / relative, destination / relative)


def _bump_release_version(destination: Path, new_version: str) -> None:
    """Reproduce release-please's mechanical bump on a copied project.

    release-please rewrites pyproject.toml and .release-please-manifest.json and
    leaves uv.lock untouched -- that omission is the bug this module guards.
    """
    current = json.loads((destination / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]

    pyproject_path = destination / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    assert pyproject.count(f'version = "{current}"') == 1
    pyproject_path.write_text(
        pyproject.replace(f'version = "{current}"', f'version = "{new_version}"'),
        encoding="utf-8",
    )

    manifest_path = destination / ".release-please-manifest.json"
    manifest_path.write_text(json.dumps({".": new_version}, indent=2) + "\n", encoding="utf-8")


def test_release_version_bump_keeps_the_lock_contract_valid(tmp_path: Path) -> None:
    """A release-please version bump must not break the lock contract.

    Guards the regression where the contract demanded uv.lock's editable root
    version equal project.version, so every release PR failed CI.
    """
    _copy_lock_inputs(tmp_path)
    _bump_release_version(tmp_path, "9.9.9")

    validate(tmp_path)


def test_lock_resolution_checker_accepts_a_bumped_release(tmp_path: Path) -> None:
    """`uv lock --check` must stay green across a release-please version bump."""
    if shutil.which("uv") is None and not _uv_is_importable():
        pytest.skip("uv is not installed")

    _copy_lock_inputs(tmp_path)
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    shutil.copytree(ROOT / "src", tmp_path / "src")
    _bump_release_version(tmp_path, "9.9.9")

    returncode, output = check(tmp_path)

    assert returncode == 0, output


def test_lock_resolution_checker_rejects_dependency_drift(tmp_path: Path) -> None:
    """Normalising the root version must not hide real dependency drift."""
    if shutil.which("uv") is None and not _uv_is_importable():
        pytest.skip("uv is not installed")

    _copy_lock_inputs(tmp_path)
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    shutil.copytree(ROOT / "src", tmp_path / "src")
    _bump_release_version(tmp_path, "9.9.9")
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace("adobepy==0.6.2", "adobepy==0.6.1"),
        encoding="utf-8",
    )

    returncode, _output = check(tmp_path)

    assert returncode != 0


def test_root_version_normalisation_rewrites_only_the_root_version(tmp_path: Path) -> None:
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    normalised = normalise_root_version(lock_text, "9.9.9")

    assert normalised != lock_text
    assert (ROOT_NAME, "9.9.9") == _editable_root(normalised)
    assert normalised.count('version = "9.9.9"') == 1


def test_root_version_normalisation_is_a_no_op_when_versions_agree() -> None:
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    _name, version = _editable_root(lock_text)

    assert normalise_root_version(lock_text, version) == lock_text


def test_root_version_normalisation_fails_closed_on_an_unknown_layout() -> None:
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    _name, version = _editable_root(lock_text)
    # Still valid TOML, but no longer the `name` then `version` layout the rewrite targets.
    reordered = lock_text.replace(
        f'name = "{ROOT_NAME}"\nversion = "{version}"',
        f'version = "{version}"\nname = "{ROOT_NAME}"',
    )

    with pytest.raises(ValueError, match="could not rewrite"):
        normalise_root_version(reordered, "9.9.9")


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
    assert "python scripts/ci/check_uv_lock_resolution.py" in lock_runs
    assert {"dependency-contract", "lock-contract"} <= set(jobs["ci-gate"]["needs"])
