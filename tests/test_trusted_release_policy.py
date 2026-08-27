from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "ci" / "check_trusted_release_policy.py"
APPROVED = ROOT / "scripts" / "ci" / "approved_release_workflow.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "trusted-release-policy.yml"
APPROVED_DIGEST = "ec9c928560e975d21d44b71f3ea6e5c3c2f1445cfbceb3f553a57f0a2256bd7a"


def _run_checker(candidate: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--candidate", str(candidate)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _workflow_document():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_base_owned_checker_accepts_the_reviewed_release_target() -> None:
    result = _run_checker(APPROVED)

    assert result.returncode == 0, result.stdout + result.stderr
    assert APPROVED_DIGEST in result.stdout


def test_base_owned_checker_rejects_the_old_main_release_workflow() -> None:
    result = _run_checker(ROOT / ".github" / "workflows" / "release.yml")

    assert result.returncode != 0
    assert "approved release policy" in result.stderr


def test_variable_upload_and_synchronized_pr_checker_cannot_replace_base_policy(tmp_path: Path) -> None:
    candidate = yaml.safe_load(APPROVED.read_text(encoding="utf-8"))
    candidate["jobs"]["attach-release-assets"]["steps"].insert(
        0,
        {
            "name": "Variable expansion upload",
            "run": 'G=gh; R=release; U=upload; $G $R $U "$TAG_NAME" release-assets/*',
        },
    )
    pr_root = tmp_path / "pull-request"
    pr_checker = pr_root / "scripts" / "ci" / "check_trusted_release_policy.py"
    pr_checker.parent.mkdir(parents=True)
    marker = tmp_path / "untrusted-code-executed"
    pr_checker.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    candidate_path = pr_root / "release.yml"
    candidate_path.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")
    synchronized_pr_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    (pr_root / "expected-policy-hash.txt").write_text(synchronized_pr_hash, encoding="utf-8")

    result = _run_checker(candidate_path, cwd=pr_root)

    assert result.returncode != 0
    assert not marker.exists()


def test_second_expansion_form_is_rejected_by_the_base_policy(tmp_path: Path) -> None:
    candidate = yaml.safe_load(APPROVED.read_text(encoding="utf-8"))
    candidate["jobs"]["attach-release-assets"]["steps"].insert(
        0,
        {
            "name": "Expansion upload",
            "run": 'EMPTY=; gh re${EMPTY}lease upload "$TAG_NAME" release-assets/*',
        },
    )
    candidate_path = tmp_path / "release.yml"
    candidate_path.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")

    result = _run_checker(candidate_path)

    assert result.returncode != 0


def test_trusted_gate_uses_only_base_code_and_pull_request_git_objects() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    document = _workflow_document()
    event = document.get("on", document.get(True))
    trigger = event["pull_request_target"]
    job = document["jobs"]["validate"]
    steps = job["steps"]
    checkout, setup, install, validate = steps

    assert document["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert job["timeout-minutes"] == 5
    assert trigger["branches"] == ["main"]
    assert "paths" not in trigger
    assert event["pull_request_review"] == {"types": ["submitted", "dismissed"]}
    assert job["if"] == "github.event.pull_request.base.ref == 'main'"
    assert [step["name"] for step in steps] == [
        "Checkout the trusted base commit",
        "Set up trusted Python",
        "Install the trusted parser dependency",
        "Extract and validate the pull request workflow as data",
    ]
    assert checkout["uses"] == "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803"
    assert checkout["with"] == {
        "ref": "${{ github.event.pull_request.base.sha }}",
        "fetch-depth": 1,
        "persist-credentials": False,
    }
    assert setup["uses"] == "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
    assert setup["with"] == {"python-version": "3.12"}
    assert install["run"] == "python -m pip install --disable-pip-version-check PyYAML==6.0.3"
    assert "secrets." not in source
    assert "refs/pull/$PR_NUMBER/head:refs/dcc-mcp-policy/pr-head" in validate["run"]
    assert "RELEASE_OID=$(python scripts/ci/check_trusted_release_policy.py" in validate["run"]
    assert 'git show "$RELEASE_OID" > "$CANDIDATE"' in validate["run"]
    assert 'test "$(git rev-parse HEAD)" = "$BASE_SHA"' in validate["run"]
    assert '--candidate "$CANDIDATE"' in validate["run"]
    assert '--base-sha "$BASE_SHA"' in validate["run"]
    assert '--candidate-sha "$FETCHED_SHA"' in validate["run"]
    assert '--repository-slug "$GITHUB_REPOSITORY"' in validate["run"]
    assert "git checkout" not in validate["run"]
    assert "git switch" not in validate["run"]
    assert "pull-request/scripts" not in source


def test_trusted_gate_has_no_unapproved_action_or_extra_step() -> None:
    job = _workflow_document()["jobs"]["validate"]
    action_steps = [step for step in job["steps"] if "uses" in step]
    run_steps = [step for step in job["steps"] if "run" in step]

    assert [step["uses"] for step in action_steps] == [
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
    ]
    assert len(run_steps) == 2
