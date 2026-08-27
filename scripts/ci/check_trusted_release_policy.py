"""Validate a release workflow using a base-branch-owned trust root."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Set

import yaml
from yaml.constructor import ConstructorError
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

ROOT = Path(__file__).resolve().parents[2]
APPROVED_RELEASE_WORKFLOW = ROOT / "scripts" / "ci" / "approved_release_workflow.yml"
APPROVED_RELEASE_WORKFLOW_SHA256 = "3fa27668fcf36339f0e449bfe8c51952e3729f3f1442ec89a8c78981c552ce3c"
MAX_WORKFLOW_BYTES = 256 * 1024
GIT_TIMEOUT_SECONDS = 30
MAX_CANDIDATE_COMMITS = 250
RELEASE_WORKFLOW_PATH = ".github/workflows/release.yml"
TRUST_ROOT_PATHS = (
    ".github/workflows/trusted-release-policy.yml",
    "scripts/ci/check_trusted_release_policy.py",
    "scripts/ci/approved_release_workflow.yml",
)
POLICY_PATHS = (*TRUST_ROOT_PATHS, RELEASE_WORKFLOW_PATH)
OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY_SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class PolicyError(ValueError):
    """The untrusted candidate does not match the approved release policy."""


class UpgradeAuthorizationRequired(PolicyError):
    """A protected policy root changed and needs an external exact-head approval."""


class TreeObject(NamedTuple):
    mode: str
    type: str
    oid: str
    path: str
    size: int
    sha256: str
    content: bytes

    def public_identity(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "type": self.type,
            "oid": self.oid,
            "size": self.size,
            "sha256": self.sha256,
        }


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


def _read_regular_bytes(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PolicyError(f"workflow input is unavailable: {exc.__class__.__name__}") from None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    if path.is_symlink() or file_attributes & reparse_flag or not stat.S_ISREG(metadata.st_mode):
        raise PolicyError("workflow input must be a regular non-symlink file")
    if metadata.st_size > MAX_WORKFLOW_BYTES:
        raise PolicyError("workflow input exceeds the trusted size limit")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PolicyError(f"workflow input is unreadable: {exc.__class__.__name__}") from None


def _read_regular_file(path: Path) -> str:
    try:
        return _read_regular_bytes(path).decode("utf-8")
    except UnicodeError as exc:
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


def _git_process(repository: Path, *arguments: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=str(repository),
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolicyError(f"git policy inspection failed: {exc.__class__.__name__}") from None


def _validate_object_id(value: str, label: str) -> str:
    if OBJECT_ID.fullmatch(value) is None:
        raise PolicyError(f"{label} must be a lowercase 40-character Git object id")
    return value


def _ensure_commit(repository: Path, oid: str, label: str) -> None:
    result = _git_process(repository, "cat-file", "-e", f"{oid}^{{commit}}")
    if result.returncode != 0:
        raise PolicyError(f"{label} commit is unavailable")


def _require_base_ancestor(repository: Path, base_sha: str, candidate_sha: str) -> None:
    result = _git_process(repository, "merge-base", "--is-ancestor", base_sha, candidate_sha)
    if result.returncode == 1:
        raise PolicyError("base commit is not an ancestor of the candidate commit")
    if result.returncode != 0:
        raise PolicyError("Git could not verify candidate ancestry")


def _tree_object(repository: Path, commit_sha: str, fixed_path: str) -> TreeObject:
    result = _git_process(repository, "ls-tree", "-z", commit_sha, "--", fixed_path)
    if result.returncode != 0:
        raise PolicyError(f"fixed policy path {fixed_path!r} could not be inspected")
    records = [record for record in result.stdout.split(b"\0") if record]
    expected_error = f"fixed policy path {fixed_path!r} must be exactly one 100644 blob"
    if len(records) != 1:
        raise PolicyError(expected_error)
    try:
        metadata, encoded_path = records[0].split(b"\t", 1)
        mode_bytes, type_bytes, oid_bytes = metadata.split(b" ")
        mode = mode_bytes.decode("ascii")
        object_type = type_bytes.decode("ascii")
        oid = oid_bytes.decode("ascii")
        path = encoded_path.decode("utf-8")
    except (UnicodeError, ValueError):
        raise PolicyError(expected_error) from None
    if mode != "100644" or object_type != "blob" or OBJECT_ID.fullmatch(oid) is None or path != fixed_path:
        raise PolicyError(expected_error)
    size_result = _git_process(repository, "cat-file", "-s", oid)
    blob_result = _git_process(repository, "cat-file", "blob", oid)
    if size_result.returncode != 0 or blob_result.returncode != 0:
        raise PolicyError(f"fixed policy object for {fixed_path!r} is unavailable")
    try:
        size = int(size_result.stdout.strip())
    except ValueError:
        raise PolicyError(f"fixed policy object size for {fixed_path!r} is invalid") from None
    if size != len(blob_result.stdout) or size <= 0 or size > MAX_WORKFLOW_BYTES:
        raise PolicyError(f"fixed policy object for {fixed_path!r} violates the size contract")
    return TreeObject(
        mode=mode,
        type=object_type,
        oid=oid,
        path=path,
        size=size,
        sha256=hashlib.sha256(blob_result.stdout).hexdigest(),
        content=blob_result.stdout,
    )


def inspect_release_object(repository: Path, candidate_sha: str) -> TreeObject:
    candidate_sha = _validate_object_id(candidate_sha, "candidate SHA")
    _ensure_commit(repository, candidate_sha, "candidate")
    return _tree_object(repository, candidate_sha, RELEASE_WORKFLOW_PATH)


def validate_tree(
    repository: Path,
    base_sha: str,
    candidate_sha: str,
    candidate_path: Path,
    *,
    upgrade_authorized: bool = False,
) -> Dict[str, Any]:
    base_sha = _validate_object_id(base_sha, "base SHA")
    candidate_sha = _validate_object_id(candidate_sha, "candidate SHA")
    _ensure_commit(repository, base_sha, "base")
    _ensure_commit(repository, candidate_sha, "candidate")
    _require_base_ancestor(repository, base_sha, candidate_sha)

    base_objects = {path: _tree_object(repository, base_sha, path) for path in POLICY_PATHS}
    candidate_objects = {path: _tree_object(repository, candidate_sha, path) for path in POLICY_PATHS}
    candidate_bytes = _read_regular_bytes(candidate_path)
    release_object = candidate_objects[RELEASE_WORKFLOW_PATH]
    if candidate_bytes != release_object.content:
        raise PolicyError("extracted release candidate does not match its inspected Git blob identity")

    changed_trust_roots = [path for path in TRUST_ROOT_PATHS if candidate_objects[path].oid != base_objects[path].oid]
    release_changed = candidate_objects[RELEASE_WORKFLOW_PATH].oid != base_objects[RELEASE_WORKFLOW_PATH].oid
    report: Dict[str, Any] = {
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "paths": {path: candidate_objects[path].public_identity() for path in POLICY_PATHS},
    }
    if not changed_trust_roots and not release_changed:
        report["outcome"] = "no-op"
        return report
    if changed_trust_roots:
        if release_changed:
            raise PolicyError("policy-root upgrades and release candidates require a separate pull request")
        if not upgrade_authorized:
            raise UpgradeAuthorizationRequired("policy-root changes require external exact-head upgrade authorization")
        report["outcome"] = "authorized-policy-upgrade"
        report["changed_trust_roots"] = changed_trust_roots
        return report

    validate_candidate(candidate_path)
    report["outcome"] = "approved-release-candidate"
    return report


def select_upgrade_approver(
    reviews: Sequence[Mapping[str, Any]],
    candidate_sha: str,
    excluded_logins: Sequence[str],
    permission_lookup: Callable[[str], str],
) -> Optional[str]:
    candidate_sha = _validate_object_id(candidate_sha, "candidate SHA")
    excluded = {login.casefold() for login in excluded_logins}
    latest_by_reviewer: Dict[str, Mapping[str, Any]] = {}
    for review in reviews:
        user = review.get("user")
        if (
            not isinstance(user, dict)
            or not isinstance(user.get("login"), str)
            or user.get("type") != "User"
            or review.get("commit_id") != candidate_sha
            or review.get("state") not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
        ):
            continue
        login = user["login"]
        review_id = review.get("id")
        if not isinstance(review_id, int):
            continue
        previous = latest_by_reviewer.get(login.casefold())
        if previous is None or review_id > previous.get("id", -1):
            latest_by_reviewer[login.casefold()] = review

    approved: List[Mapping[str, Any]] = []
    blocked: List[str] = []
    for review in latest_by_reviewer.values():
        login = review["user"]["login"]
        if login.casefold() in excluded or review.get("state") == "DISMISSED":
            continue
        if permission_lookup(login) not in {"admin", "maintain"}:
            continue
        if review.get("state") == "CHANGES_REQUESTED":
            blocked.append(login)
        else:
            approved.append(review)
    if blocked:
        raise PolicyError("an eligible human maintainer has active exact-head changes requested")
    if approved:
        latest_approval = max(approved, key=lambda review: review["id"])
        return latest_approval["user"]["login"]
    return None


def _candidate_commit_shas(repository: Path, base_sha: str, candidate_sha: str) -> List[str]:
    base_sha = _validate_object_id(base_sha, "base SHA")
    candidate_sha = _validate_object_id(candidate_sha, "candidate SHA")
    _ensure_commit(repository, base_sha, "base")
    _ensure_commit(repository, candidate_sha, "candidate")
    _require_base_ancestor(repository, base_sha, candidate_sha)
    result = _git_process(repository, "rev-list", "--reverse", f"{base_sha}..{candidate_sha}")
    if result.returncode != 0:
        raise PolicyError("Git could not enumerate the exact candidate commit range")
    try:
        commit_shas = [line.decode("ascii") for line in result.stdout.splitlines() if line]
    except UnicodeError:
        raise PolicyError("Git returned an invalid candidate commit identity") from None
    if not commit_shas or len(commit_shas) > MAX_CANDIDATE_COMMITS:
        raise PolicyError("exact candidate commit range violates the bounded commit limit")
    if any(OBJECT_ID.fullmatch(sha) is None for sha in commit_shas) or commit_shas[-1] != candidate_sha:
        raise PolicyError("Git returned an invalid exact candidate commit range")
    return commit_shas


def candidate_commit_participants(
    repository: Path,
    base_sha: str,
    candidate_sha: str,
    api_commits: Sequence[Mapping[str, Any]],
) -> Set[str]:
    local_shas = _candidate_commit_shas(repository, base_sha, candidate_sha)
    api_shas = [commit.get("sha") for commit in api_commits]
    if api_shas != local_shas:
        raise PolicyError("GitHub commits do not match the exact candidate commit range")
    participants: Set[str] = set()
    for commit in api_commits:
        identities: List[str] = []
        for role in ("author", "committer"):
            identity = commit.get(role)
            if not isinstance(identity, dict) or not isinstance(identity.get("login"), str) or not identity["login"]:
                raise PolicyError("candidate commit author and committer identities must be linked to GitHub users")
            identities.append(identity["login"])
        participants.update(identities)
    return participants


def _github_json(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "dcc-mcp-photoshop-trusted-release-policy",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=GIT_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        raise PolicyError(f"GitHub upgrade authorization lookup failed: {exc.__class__.__name__}") from None


def _live_upgrade_approver(
    repository: Path,
    repository_slug: str,
    pull_request_number: int,
    base_sha: str,
    candidate_sha: str,
    pull_request_author: str,
    token: str,
) -> Optional[str]:
    if REPOSITORY_SLUG.fullmatch(repository_slug) is None or pull_request_number <= 0 or not token:
        raise PolicyError("upgrade authorization context is invalid")
    local_commits = _candidate_commit_shas(repository, base_sha, candidate_sha)
    api_commits: List[Mapping[str, Any]] = []
    for page in range(1, 4):
        value = _github_json(
            f"/repos/{repository_slug}/pulls/{pull_request_number}/commits?per_page=100&page={page}",
            token,
        )
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PolicyError("GitHub candidate commits response is invalid")
        api_commits.extend(value)
        if len(value) < 100:
            break
    if len(api_commits) > MAX_CANDIDATE_COMMITS or len(api_commits) != len(local_commits):
        raise PolicyError("GitHub commits do not match the exact candidate commit range")
    excluded_logins = candidate_commit_participants(repository, base_sha, candidate_sha, api_commits)
    excluded_logins.add(pull_request_author)

    reviews: List[Mapping[str, Any]] = []
    for page in range(1, 11):
        value = _github_json(
            f"/repos/{repository_slug}/pulls/{pull_request_number}/reviews?per_page=100&page={page}",
            token,
        )
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PolicyError("GitHub upgrade reviews response is invalid")
        reviews.extend(value)
        if len(value) < 100:
            break
    else:
        raise PolicyError("GitHub upgrade reviews exceed the bounded review limit")

    def permission_lookup(login: str) -> str:
        encoded_login = urllib.parse.quote(login, safe="")
        value = _github_json(f"/repos/{repository_slug}/collaborators/{encoded_login}/permission", token)
        if not isinstance(value, dict) or not isinstance(value.get("permission"), str):
            raise PolicyError("GitHub collaborator permission response is invalid")
        return value["permission"]

    return select_upgrade_approver(reviews, candidate_sha, excluded_logins, permission_lookup)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, help="untrusted release workflow extracted as data")
    parser.add_argument("--repository", type=Path, help="trusted base checkout containing fetched Git objects")
    parser.add_argument("--base-sha", help="exact pull-request base commit")
    parser.add_argument("--candidate-sha", help="exact fetched pull-request head commit")
    parser.add_argument("--repository-slug", help="GitHub OWNER/REPO for approval lookup")
    parser.add_argument("--pull-request-number", type=int, help="pull-request number for approval lookup")
    parser.add_argument("--pull-request-author", help="pull-request author login")
    parser.add_argument("--inspect-release", action="store_true", help="print the validated release blob object id")
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.inspect_release:
            if arguments.repository is None or arguments.candidate_sha is None:
                raise PolicyError("release inspection requires repository and candidate SHA")
            print(inspect_release_object(arguments.repository, arguments.candidate_sha).oid)
            return 0
        if arguments.candidate is None:
            raise PolicyError("a candidate workflow path is required")
        if arguments.repository is None:
            validate_candidate(arguments.candidate)
        else:
            if arguments.base_sha is None or arguments.candidate_sha is None:
                raise PolicyError("tree validation requires exact base and candidate SHAs")
            try:
                report = validate_tree(
                    arguments.repository,
                    arguments.base_sha,
                    arguments.candidate_sha,
                    arguments.candidate,
                )
            except UpgradeAuthorizationRequired:
                if (
                    arguments.repository_slug is None
                    or arguments.pull_request_number is None
                    or arguments.pull_request_author is None
                ):
                    raise PolicyError("policy-root changes require complete external approval context") from None
                approver = _live_upgrade_approver(
                    arguments.repository,
                    arguments.repository_slug,
                    arguments.pull_request_number,
                    arguments.base_sha,
                    arguments.candidate_sha,
                    arguments.pull_request_author,
                    os.environ.get("GH_TOKEN", ""),
                )
                if approver is None:
                    raise PolicyError(
                        "policy-root changes lack an exact-head independent maintainer approval"
                    ) from None
                report = validate_tree(
                    arguments.repository,
                    arguments.base_sha,
                    arguments.candidate_sha,
                    arguments.candidate,
                    upgrade_authorized=True,
                )
                report["upgrade_approver"] = approver
            print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    except PolicyError as exc:
        print(f"trusted release policy failed: {exc}", file=sys.stderr)
        return 1
    print(f"trusted release policy passed for approved digest {APPROVED_RELEASE_WORKFLOW_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
