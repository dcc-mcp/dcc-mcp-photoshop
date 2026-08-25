from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci import check_trusted_release_policy as policy

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "scripts" / "ci" / "approved_release_workflow.yml"
RELEASE_PATH = Path(".github/workflows/release.yml")
TRUST_ROOTS = (
    Path(".github/workflows/trusted-release-policy.yml"),
    Path("scripts/ci/check_trusted_release_policy.py"),
    Path("scripts/ci/approved_release_workflow.yml"),
)


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_policy_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "Policy Test")
    _git(repository, "config", "user.email", "policy@example.invalid")
    _git(repository, "config", "core.autocrlf", "false")
    for relative in TRUST_ROOTS:
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    release = repository / RELEASE_PATH
    release.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APPROVED, release)
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "base policy")
    return repository, _git(repository, "rev-parse", "HEAD")


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "-A")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _review(review_id: int, state: str, commit_id: str, login: str, user_type: str = "User") -> dict:
    return {
        "id": review_id,
        "state": state,
        "commit_id": commit_id,
        "user": {"login": login, "type": user_type},
    }


def _validate_tree(
    repository: Path,
    base_sha: str,
    candidate_sha: str,
    candidate_output: Path,
    *,
    upgrade_authorized: bool = False,
):
    validator = getattr(policy, "validate_tree", None)
    if validator is None:
        policy.validate_candidate(candidate_output)
        return {}
    return validator(
        repository,
        base_sha,
        candidate_sha,
        candidate_output,
        upgrade_authorized=upgrade_authorized,
    )


def test_tree_policy_binds_every_fixed_path_to_mode_object_size_and_digest(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)

    report = _validate_tree(repository, base_sha, base_sha, repository / RELEASE_PATH)

    assert set(report["paths"]) == {*(str(path).replace("\\", "/") for path in TRUST_ROOTS), RELEASE_PATH.as_posix()}
    for identity in report["paths"].values():
        assert identity["mode"] == "100644"
        assert identity["type"] == "blob"
        assert len(identity["oid"]) == 40
        assert identity["size"] > 0
        assert len(identity["sha256"]) == 64
    assert report["outcome"] == "no-op"


def test_workflow_cli_inspects_then_validates_the_exact_git_blob(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    checker = Path(policy.__file__).resolve()
    inspect = subprocess.run(
        [
            sys.executable,
            str(checker),
            "--inspect-release",
            "--repository",
            str(repository),
            "--candidate-sha",
            base_sha,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    expected_oid = _git(repository, "rev-parse", f"{base_sha}:{RELEASE_PATH.as_posix()}")
    assert inspect.returncode == 0, inspect.stdout + inspect.stderr
    assert inspect.stdout.strip() == expected_oid

    validate = subprocess.run(
        [
            sys.executable,
            str(checker),
            "--candidate",
            str(repository / RELEASE_PATH),
            "--repository",
            str(repository),
            "--base-sha",
            base_sha,
            "--candidate-sha",
            base_sha,
            "--repository-slug",
            "dcc-mcp/dcc-mcp-photoshop",
            "--pull-request-number",
            "110",
            "--pull-request-author",
            "author",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert '"outcome":"no-op"' in validate.stdout


@pytest.mark.parametrize("relative", TRUST_ROOTS)
def test_ordinary_lane_rejects_replaced_trust_roots_without_executing_them(tmp_path: Path, relative: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    marker = tmp_path / "untrusted-marker"
    replacement = repository / relative
    if relative.suffix == ".py":
        replacement.write_text(
            replacement.read_text(encoding="utf-8")
            + f"\nPath({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
            encoding="utf-8",
        )
    else:
        replacement.write_text(
            replacement.read_text(encoding="utf-8") + "\n# unreviewed replacement\n", encoding="utf-8"
        )
    candidate_sha = _commit(repository, f"replace {relative}")

    with pytest.raises(policy.PolicyError, match="upgrade authorization"):
        _validate_tree(repository, base_sha, candidate_sha, repository / RELEASE_PATH)
    assert not marker.exists()


@pytest.mark.parametrize("mutation", ["permissions", "action"])
def test_ordinary_lane_rejects_trusted_workflow_permission_or_action_changes(tmp_path: Path, mutation: str) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    workflow_path = repository / TRUST_ROOTS[0]
    document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    if mutation == "permissions":
        document["permissions"] = {"contents": "write"}
    else:
        document["jobs"]["validate"]["steps"][0]["uses"] = "attacker/checkout@0000000000000000000000000000000000000000"
    workflow_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    candidate_sha = _commit(repository, mutation)

    with pytest.raises(policy.PolicyError, match="upgrade authorization"):
        _validate_tree(repository, base_sha, candidate_sha, repository / RELEASE_PATH)


def test_synchronized_checker_and_snapshot_cannot_self_authorize_or_execute(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    marker = tmp_path / "synchronized-marker"
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(
        checker.read_text(encoding="utf-8") + f"\nPath({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    snapshot = repository / TRUST_ROOTS[2]
    snapshot.write_text(snapshot.read_text(encoding="utf-8") + "\n# synchronized digest\n", encoding="utf-8")
    candidate_sha = _commit(repository, "synchronized trust roots")

    with pytest.raises(policy.PolicyError, match="upgrade authorization"):
        _validate_tree(repository, base_sha, candidate_sha, repository / RELEASE_PATH)
    assert not marker.exists()


@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_ordinary_lane_rejects_missing_or_renamed_trust_roots(tmp_path: Path, operation: str) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    target = repository / TRUST_ROOTS[1]
    if operation == "delete":
        target.unlink()
    else:
        target.rename(target.with_suffix(".moved"))
    candidate_sha = _commit(repository, operation)

    with pytest.raises(policy.PolicyError, match="fixed policy path"):
        _validate_tree(repository, base_sha, candidate_sha, repository / RELEASE_PATH)


def test_exact_head_maintainer_upgrade_never_executes_candidate_code(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    marker = tmp_path / "untrusted-marker"
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(
        checker.read_text(encoding="utf-8") + f"\nPath({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    candidate_sha = _commit(repository, "authorized policy upgrade")

    report = _validate_tree(
        repository,
        base_sha,
        candidate_sha,
        repository / RELEASE_PATH,
        upgrade_authorized=True,
    )

    assert report["outcome"] == "authorized-policy-upgrade"
    assert not marker.exists()


def test_upgrade_approval_requires_a_distinct_exact_head_human_maintainer() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "APPROVED", "b" * 40, "stale-reviewer"),
        _review(2, "APPROVED", head, "pull-request-author"),
        _review(3, "APPROVED", head, "write-only"),
        _review(4, "APPROVED", head, "maintainer"),
    ]
    permissions = {
        "stale-reviewer": "admin",
        "pull-request-author": "admin",
        "write-only": "write",
        "maintainer": "maintain",
    }

    reviewer = policy.select_upgrade_approver(
        reviews,
        head,
        {"pull-request-author", "commit-author", "commit-committer"},
        permissions.__getitem__,
    )

    assert reviewer == "maintainer"


def test_bot_and_non_user_approvals_never_authorize_upgrade() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "APPROVED", head, "release-bot", "Bot"),
        _review(2, "APPROVED", head, "release-team", "Organization"),
    ]

    reviewer = policy.select_upgrade_approver(reviews, head, {"author"}, lambda _login: "admin")

    assert reviewer is None


def test_candidate_commit_authors_and_committers_cannot_approve_upgrade() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "APPROVED", head, "commit-author"),
        _review(2, "APPROVED", head, "commit-committer"),
        _review(3, "APPROVED", head, "independent-maintainer"),
    ]

    reviewer = policy.select_upgrade_approver(
        reviews,
        head,
        {"pull-request-author", "commit-author", "commit-committer"},
        lambda _login: "maintain",
    )

    assert reviewer == "independent-maintainer"


def test_exact_head_changes_requested_by_any_eligible_maintainer_blocks_other_approval() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "APPROVED", head, "approver"),
        _review(2, "CHANGES_REQUESTED", head, "blocker"),
    ]

    with pytest.raises(policy.PolicyError, match="changes requested"):
        policy.select_upgrade_approver(reviews, head, set(), lambda _login: "admin")


def test_latest_exact_head_decisive_review_controls_mixed_order() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "CHANGES_REQUESTED", head, "maintainer"),
        _review(2, "COMMENTED", head, "maintainer"),
        _review(3, "APPROVED", head, "maintainer"),
    ]

    reviewer = policy.select_upgrade_approver(reviews, head, set(), lambda _login: "maintain")

    assert reviewer == "maintainer"


def test_later_exact_head_changes_requested_supersedes_approval() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "APPROVED", head, "maintainer"),
        _review(2, "APPROVED", head, "other-maintainer"),
        _review(3, "CHANGES_REQUESTED", head, "maintainer"),
    ]

    with pytest.raises(policy.PolicyError, match="changes requested"):
        policy.select_upgrade_approver(reviews, head, set(), lambda _login: "admin")


def test_dismissed_approval_does_not_authorize_upgrade() -> None:
    head = "a" * 40
    reviews = [_review(1, "DISMISSED", head, "maintainer")]

    reviewer = policy.select_upgrade_approver(reviews, head, set(), lambda _login: "admin")

    assert reviewer is None


def test_stale_and_dismissed_changes_requested_do_not_block_exact_head_approval() -> None:
    head = "a" * 40
    reviews = [
        _review(1, "CHANGES_REQUESTED", "b" * 40, "stale-reviewer"),
        _review(2, "DISMISSED", head, "dismissed-reviewer"),
        _review(3, "APPROVED", head, "maintainer"),
    ]

    reviewer = policy.select_upgrade_approver(reviews, head, set(), lambda _login: "admin")

    assert reviewer == "maintainer"


def test_candidate_commit_api_is_bound_to_exact_local_range(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(checker.read_text(encoding="utf-8") + "\n# upgrade\n", encoding="utf-8")
    candidate_sha = _commit(repository, "policy upgrade")
    api_commits = [
        {
            "sha": candidate_sha,
            "author": {"login": "commit-author", "type": "User"},
            "committer": {"login": "commit-committer", "type": "User"},
        }
    ]

    participants = policy.candidate_commit_participants(repository, base_sha, candidate_sha, api_commits)

    assert participants == {"commit-author", "commit-committer"}
    with pytest.raises(policy.PolicyError, match="exact candidate commit range"):
        policy.candidate_commit_participants(
            repository,
            base_sha,
            candidate_sha,
            [{**api_commits[0], "sha": "f" * 40}],
        )


def test_candidate_commit_identity_must_be_linked_to_github_users(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(checker.read_text(encoding="utf-8") + "\n# upgrade\n", encoding="utf-8")
    candidate_sha = _commit(repository, "policy upgrade")

    with pytest.raises(policy.PolicyError, match="author and committer identities"):
        policy.candidate_commit_participants(
            repository,
            base_sha,
            candidate_sha,
            [{"sha": candidate_sha, "author": None, "committer": {"login": "committer", "type": "User"}}],
        )


def test_live_upgrade_lookup_excludes_exact_candidate_commit_participants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(checker.read_text(encoding="utf-8") + "\n# upgrade\n", encoding="utf-8")
    candidate_sha = _commit(repository, "policy upgrade")

    def github_json(path: str, _token: str):
        if "/commits?" in path:
            return [
                {
                    "sha": candidate_sha,
                    "author": {"login": "commit-author", "type": "User"},
                    "committer": {"login": "commit-committer", "type": "User"},
                }
            ]
        if "/reviews?" in path:
            return [
                {
                    "id": 1,
                    "state": "APPROVED",
                    "commit_id": candidate_sha,
                    "user": {"login": "commit-author", "type": "User"},
                },
                {
                    "id": 2,
                    "state": "APPROVED",
                    "commit_id": candidate_sha,
                    "user": {"login": "independent-maintainer", "type": "User"},
                },
            ]
        if "/collaborators/independent-maintainer/permission" in path:
            return {"permission": "maintain"}
        raise AssertionError(f"unexpected GitHub API path: {path}")

    monkeypatch.setattr(policy, "_github_json", github_json)

    reviewer = policy._live_upgrade_approver(
        repository,
        "dcc-mcp/dcc-mcp-photoshop",
        110,
        base_sha,
        candidate_sha,
        "pull-request-author",
        "token",
    )

    assert reviewer == "independent-maintainer"


def test_codeowners_covers_every_release_policy_trust_root() -> None:
    source = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    rules = {line.split()[0]: line.split()[1:] for line in source.splitlines() if line and not line.startswith("#")}

    for path in (*TRUST_ROOTS, RELEASE_PATH):
        assert f"/{path.as_posix()}" in rules
        assert rules[f"/{path.as_posix()}"] == ["@loonghao"]


def test_upgrade_cannot_change_policy_and_release_candidate_together(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    checker = repository / TRUST_ROOTS[1]
    checker.write_text(checker.read_text(encoding="utf-8") + "\n# upgrade\n", encoding="utf-8")
    release = repository / RELEASE_PATH
    release.write_text("# changed together\n" + release.read_text(encoding="utf-8"), encoding="utf-8")
    candidate_sha = _commit(repository, "self authorize release")

    with pytest.raises(policy.PolicyError, match="separate pull request"):
        _validate_tree(
            repository,
            base_sha,
            candidate_sha,
            release,
            upgrade_authorized=True,
        )


@pytest.mark.parametrize("mode", ["100755", "120000", "160000", "040000", "missing"])
def test_release_candidate_must_be_one_regular_non_executable_blob(tmp_path: Path, mode: str) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    release = repository / RELEASE_PATH
    same_bytes = tmp_path / "same-bytes-release.yml"
    shutil.copy2(release, same_bytes)
    if mode == "100755":
        _git(repository, "update-index", "--chmod=+x", RELEASE_PATH.as_posix())
    elif mode == "120000":
        release.unlink()
        try:
            release.symlink_to(same_bytes)
        except OSError as exc:  # pragma: no cover - local Windows policy may deny symlinks
            pytest.skip(f"file symlinks unavailable: {exc.__class__.__name__}")
        _git(repository, "add", RELEASE_PATH.as_posix())
    elif mode == "160000":
        release.unlink()
        _git(repository, "update-index", "--add", "--cacheinfo", f"160000,{base_sha},{RELEASE_PATH.as_posix()}")
    elif mode == "040000":
        release.unlink()
        release.mkdir()
        _write(release / "nested.yml", APPROVED.read_text(encoding="utf-8"))
        _git(repository, "add", RELEASE_PATH.as_posix())
    else:
        _git(repository, "rm", RELEASE_PATH.as_posix())
    if mode not in {"120000", "160000", "040000", "missing"}:
        _git(repository, "commit", "-m", f"release mode {mode}")
    else:
        _git(repository, "commit", "-m", f"release mode {mode}")
    candidate_sha = _git(repository, "rev-parse", "HEAD")

    with pytest.raises(policy.PolicyError, match="100644 blob"):
        _validate_tree(repository, base_sha, candidate_sha, same_bytes)


def test_stale_or_unfetchable_candidate_commit_fails_closed(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    _git(repository, "checkout", "--orphan", "stale")
    _git(repository, "rm", "-rf", ".")
    for relative in (*TRUST_ROOTS, RELEASE_PATH):
        source = ROOT / relative if relative != RELEASE_PATH else APPROVED
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    stale_sha = _commit(repository, "stale candidate")

    with pytest.raises(policy.PolicyError, match="base commit is not an ancestor"):
        _validate_tree(repository, base_sha, stale_sha, repository / RELEASE_PATH)
    with pytest.raises(policy.PolicyError, match="candidate commit is unavailable"):
        _validate_tree(repository, base_sha, "0" * 40, repository / RELEASE_PATH)


@pytest.mark.parametrize("mutation", ["wrong-job", "duplicate-key", "variable-upload"])
def test_release_candidate_structural_bypasses_are_rejected(tmp_path: Path, mutation: str) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    release = repository / RELEASE_PATH
    if mutation == "duplicate-key":
        release.write_text("name: duplicate\n" + release.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        document = yaml.safe_load(release.read_text(encoding="utf-8"))
        if mutation == "wrong-job":
            document["jobs"]["unexpected-publisher"] = {"runs-on": "ubuntu-latest", "steps": [{"run": "true"}]}
        else:
            document["jobs"]["attach-release-assets"]["steps"].insert(
                0,
                {"run": 'G=gh; R=release; U=upload; $G $R $U "$TAG_NAME" release-assets/*'},
            )
        release.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    candidate_sha = _commit(repository, mutation)

    with pytest.raises(policy.PolicyError, match="approved release policy|workflow YAML"):
        _validate_tree(repository, base_sha, candidate_sha, release)


def test_comment_only_release_change_keeps_the_canonical_policy(tmp_path: Path) -> None:
    repository, base_sha = _init_policy_repository(tmp_path)
    release = repository / RELEASE_PATH
    release.write_text("# reviewed comment\n" + release.read_text(encoding="utf-8"), encoding="utf-8")
    candidate_sha = _commit(repository, "comment only")

    report = _validate_tree(repository, base_sha, candidate_sha, release)

    assert report["outcome"] == "approved-release-candidate"


def test_trusted_workflow_handles_forks_without_fetching_or_executing_head_code() -> None:
    source = (ROOT / ".github/workflows/trusted-release-policy.yml").read_text(encoding="utf-8")
    document = yaml.safe_load(source)
    event = document.get("on", document.get(True))
    run = document["jobs"]["validate"]["steps"][-1]["run"]

    assert "paths" not in event["pull_request_target"]
    assert "pull_request_review" in event
    assert "refs/pull/$PR_NUMBER/head" in run
    assert "--depth=1" not in run
    assert "--filter=blob:limit=262145" in run
    assert document["jobs"]["validate"]["steps"][-1]["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert "head.repo" not in source
    assert "git checkout" not in run
    assert "git switch" not in run
    assert "secrets." not in source
