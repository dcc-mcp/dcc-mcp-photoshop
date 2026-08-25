"""Fail closed when release metadata and the checked-in uv lock diverge."""

from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.8-3.10
    import tomli as tomllib


ROOT_NAME = "dcc-mcp-photoshop"
TRUSTED_ADOBEPY = "0.6.2"
CORE_SPECIFIER = ">=0.20.14,<1.0.0"
FINAL_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _final_version(value: Any, label: str) -> str:
    version = _string(value, label)
    if FINAL_VERSION.fullmatch(version) is None:
        raise ValueError(f"{label} must be a final X.Y.Z version")
    return version


def _version_tuple(version: str) -> Tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _read_regular_text(path: Path, label: str) -> str:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} cannot be inspected: {exc.__class__.__name__}") from None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(file_stat, "st_file_attributes", 0)
    if path.is_symlink() or file_attributes & reparse_flag or not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"{label} must be a non-symlink regular file")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"{label} is unreadable: {exc.__class__.__name__}") from None


def _read_regular_toml(path: Path, label: str) -> Mapping[str, Any]:
    try:
        return _mapping(tomllib.loads(_read_regular_text(path, label)), label)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{label} is invalid TOML: {exc.__class__.__name__}") from None


def _dependency_map(values: Sequence[Any], label: str) -> Dict[str, List[Mapping[str, Any]]]:
    result: Dict[str, List[Mapping[str, Any]]] = {}
    for index, value in enumerate(values):
        entry = _mapping(value, f"{label}[{index}]")
        name = _string(entry.get("name"), f"{label}[{index}].name")
        result.setdefault(name, []).append(entry)
    return result


def validate(root: Path) -> None:
    pyproject = _read_regular_toml(root / "pyproject.toml", "pyproject.toml")
    lock = _read_regular_toml(root / "uv.lock", "uv.lock")

    project = _mapping(pyproject.get("project"), "pyproject.toml project")
    if _string(project.get("name"), "project.name") != ROOT_NAME:
        raise ValueError(f"project.name must be {ROOT_NAME!r}")
    project_version = _final_version(project.get("version"), "project.version")
    project_dependencies = _list(project.get("dependencies"), "project.dependencies")
    if project_dependencies.count(f"adobepy=={TRUSTED_ADOBEPY}") != 1:
        raise ValueError(f"project.dependencies must contain exactly one adobepy=={TRUSTED_ADOBEPY}")
    if project_dependencies.count(f"dcc-mcp-core{CORE_SPECIFIER}") != 1:
        raise ValueError(f"project.dependencies must contain exactly one dcc-mcp-core{CORE_SPECIFIER}")

    packages = _list(lock.get("package"), "uv.lock package")
    package_maps = [_mapping(value, f"uv.lock package[{index}]") for index, value in enumerate(packages)]
    editable_roots = [
        package for package in package_maps if _mapping(package.get("source"), "package.source").get("editable") == "."
    ]
    if len(editable_roots) != 1:
        raise ValueError("uv.lock must contain exactly one source.editable='.' root")
    editable_root = editable_roots[0]
    if _string(editable_root.get("name"), "editable root name") != ROOT_NAME:
        raise ValueError(f"editable root must be {ROOT_NAME!r}")
    if _final_version(editable_root.get("version"), "editable root version") != project_version:
        raise ValueError("editable root version must match project.version")

    locked_by_name: Dict[str, List[Mapping[str, Any]]] = {}
    for package in package_maps:
        name = _string(package.get("name"), "package.name")
        locked_by_name.setdefault(name, []).append(package)

    adobepy_packages = locked_by_name.get("adobepy", [])
    if len(adobepy_packages) != 1:
        raise ValueError("uv.lock must contain exactly one adobepy package")
    if _final_version(adobepy_packages[0].get("version"), "adobepy version") != TRUSTED_ADOBEPY:
        raise ValueError(f"uv.lock must resolve adobepy=={TRUSTED_ADOBEPY}")

    core_packages = locked_by_name.get("dcc-mcp-core", [])
    if len(core_packages) != 1:
        raise ValueError("uv.lock must contain exactly one dcc-mcp-core package")
    core_version = _final_version(core_packages[0].get("version"), "dcc-mcp-core version")
    if not ((0, 20, 14) <= _version_tuple(core_version) < (1, 0, 0)):
        raise ValueError(f"uv.lock dcc-mcp-core {core_version} is outside {CORE_SPECIFIER}")

    root_dependencies = _dependency_map(
        _list(editable_root.get("dependencies"), "editable root dependencies"),
        "editable root dependencies",
    )
    if {"adobepy", "dcc-mcp-core"} - set(root_dependencies):
        raise ValueError("editable root dependencies must include adobepy and dcc-mcp-core")

    metadata = _mapping(editable_root.get("metadata"), "editable root metadata")
    requires_dist = _dependency_map(
        _list(metadata.get("requires-dist"), "editable root metadata.requires-dist"),
        "editable root metadata.requires-dist",
    )
    adobepy_requires = requires_dist.get("adobepy", [])
    if len(adobepy_requires) != 1 or adobepy_requires[0].get("specifier") != f"=={TRUSTED_ADOBEPY}":
        raise ValueError(f"uv.lock root metadata must require adobepy=={TRUSTED_ADOBEPY}")
    core_requires = requires_dist.get("dcc-mcp-core", [])
    if len(core_requires) != 1 or core_requires[0].get("specifier") != CORE_SPECIFIER:
        raise ValueError(f"uv.lock root metadata must require dcc-mcp-core{CORE_SPECIFIER}")

    manifest_path = root / ".release-please-manifest.json"
    try:
        manifest = _mapping(json.loads(_read_regular_text(manifest_path, "release manifest")), "release manifest")
    except json.JSONDecodeError as exc:
        raise ValueError(f"release manifest is invalid JSON: {exc.__class__.__name__}") from None
    if _final_version(manifest.get("."), "release manifest root version") != project_version:
        raise ValueError("release manifest root version must match project.version")


def main() -> int:
    try:
        validate(Path(__file__).resolve().parents[2])
    except ValueError as exc:
        print(f"uv lock contract failed: {exc}", file=sys.stderr)
        return 1
    print("uv lock contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
