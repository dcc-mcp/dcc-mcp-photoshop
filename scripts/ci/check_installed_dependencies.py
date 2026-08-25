"""Verify the dependency versions selected by a real package installation."""

from __future__ import annotations

import re
import sys
from importlib import metadata

ROOT_DISTRIBUTION = "dcc-mcp-photoshop"
TRUSTED_ADOBEPY = "0.6.2"
CORE_SPECIFIER = ">=0.20.14,<1.0.0"
FINAL_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


def _runtime_requirement(name: str) -> str:
    values = metadata.requires(ROOT_DISTRIBUTION)
    if values is None:
        raise ValueError(f"{ROOT_DISTRIBUTION} has no installed requirements metadata")
    matching = []
    for value in values:
        requirement, separator, _marker = value.partition(";")
        if separator:
            continue
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
        if match is not None and match.group(0).lower().replace("_", "-") == name:
            matching.append(requirement)
    if len(matching) != 1:
        raise ValueError(f"{ROOT_DISTRIBUTION} must declare exactly one unconditional {name} requirement")
    return matching[0]


def _version_tuple(value: str, label: str):
    if FINAL_VERSION.fullmatch(value) is None:
        raise ValueError(f"{label} must be a final X.Y.Z version")
    return tuple(int(part) for part in value.split("."))


def validate() -> None:
    adobepy_requirement = _runtime_requirement("adobepy")
    if adobepy_requirement != f"adobepy=={TRUSTED_ADOBEPY}":
        raise ValueError(f"installed metadata must pin adobepy=={TRUSTED_ADOBEPY}")
    adobepy_version = metadata.version("adobepy")
    if adobepy_version != TRUSTED_ADOBEPY:
        raise ValueError(f"resolver selected untrusted adobepy {adobepy_version}")

    core_requirement = _runtime_requirement("dcc-mcp-core")
    core_clauses = set(core_requirement[len("dcc-mcp-core") :].split(","))
    if core_clauses != {">=0.20.14", "<1.0.0"}:
        raise ValueError(f"installed metadata must require dcc-mcp-core{CORE_SPECIFIER}")
    core_version = metadata.version("dcc-mcp-core")
    if not ((0, 20, 14) <= _version_tuple(core_version, "dcc-mcp-core version") < (1, 0, 0)):
        raise ValueError(f"resolver selected unsupported dcc-mcp-core {core_version}")


def main() -> int:
    try:
        validate()
    except (ValueError, metadata.PackageNotFoundError) as exc:
        print(f"installed dependency contract failed: {exc}", file=sys.stderr)
        return 1
    print(
        "installed dependency contract passed: "
        f"adobepy={metadata.version('adobepy')} core={metadata.version('dcc-mcp-core')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
