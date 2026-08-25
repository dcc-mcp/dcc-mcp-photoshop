"""Validate a release workflow using a base-branch-owned trust root."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml
from yaml.constructor import ConstructorError
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

ROOT = Path(__file__).resolve().parents[2]
APPROVED_RELEASE_HEAD = "9a7fd52009000b6f56649b4113cbc453edaab1a5"
APPROVED_RELEASE_WORKFLOW = ROOT / "scripts" / "ci" / "approved_release_workflow.yml"
APPROVED_RELEASE_WORKFLOW_SHA256 = "a3b38a10c6caab17219f3eeea2a8fab0a1f6c3a93d770a00d5280f74a5e40da1"
MAX_WORKFLOW_BYTES = 256 * 1024


class PolicyError(ValueError):
    """The untrusted candidate does not match the approved release policy."""


class StrictWorkflowLoader(yaml.SafeLoader):
    """Safe YAML loader with YAML 1.2 booleans and unique string keys."""


StrictWorkflowLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for first_character, resolvers in list(StrictWorkflowLoader.yaml_implicit_resolvers.items()):
    StrictWorkflowLoader.yaml_implicit_resolvers[first_character] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
StrictWorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _construct_unique_mapping(
    loader: StrictWorkflowLoader,
    node: MappingNode,
    deep: bool = False,
) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError(None, None, "workflow mapping keys must be strings", key_node.start_mark)
        if key in mapping:
            raise ConstructorError(None, None, f"duplicate workflow key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictWorkflowLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _read_regular_file(path: Path) -> str:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PolicyError(f"workflow input is unavailable: {exc.__class__.__name__}") from None
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise PolicyError("workflow input must be a regular non-symlink file")
    if metadata.st_size > MAX_WORKFLOW_BYTES:
        raise PolicyError("workflow input exceeds the trusted size limit")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyError(f"workflow input is unreadable: {exc.__class__.__name__}") from None


def _load_workflow(path: Path) -> Mapping[str, Any]:
    source = _read_regular_file(path)
    try:
        if any(isinstance(event, AliasEvent) for event in yaml.parse(source, Loader=StrictWorkflowLoader)):
            raise PolicyError("workflow aliases are not allowed in the trusted policy")
        documents = list(yaml.load_all(source, Loader=StrictWorkflowLoader))
    except yaml.YAMLError as exc:
        raise PolicyError(f"workflow YAML is invalid: {exc.__class__.__name__}") from None
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise PolicyError("workflow must contain exactly one mapping document")
    return documents[0]


def _normalize_run(value: Any) -> str:
    normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines: List[str] = []
    for line in normalized.split("\n"):
        clean = line.rstrip()
        if not clean.strip() or clean.lstrip().startswith("#"):
            continue
        lines.append(clean)
    return "\n".join(lines)


def _canonicalize(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {child_key: _canonicalize(value[child_key], child_key) for child_key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if key == "run":
        return _normalize_run(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise PolicyError(f"workflow contains unsupported value type {value.__class__.__name__}")


def release_workflow_digest(path: Path) -> str:
    canonical = _canonicalize(_load_workflow(path))
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_candidate(path: Path) -> None:
    approved_digest = release_workflow_digest(APPROVED_RELEASE_WORKFLOW)
    if approved_digest != APPROVED_RELEASE_WORKFLOW_SHA256:
        raise PolicyError("base-owned approved release policy snapshot is inconsistent")
    if release_workflow_digest(path) != APPROVED_RELEASE_WORKFLOW_SHA256:
        raise PolicyError("candidate does not match the approved release policy")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True, help="untrusted release workflow extracted as data")
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        validate_candidate(arguments.candidate)
    except PolicyError as exc:
        print(f"trusted release policy failed: {exc}", file=sys.stderr)
        return 1
    print(f"trusted release policy passed for approved target {APPROVED_RELEASE_HEAD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
