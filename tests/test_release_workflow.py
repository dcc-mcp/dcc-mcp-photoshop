from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# The approved snapshot is the policy source of truth that release.yml is copied from.
APPROVED_SNAPSHOT = Path("scripts/ci/approved_release_workflow.yml")
BARE_DIGEST = "a" * 64
DIGEST_ASSERTION = re.compile(r"\[\[ \"\$ARTIFACT_DIGEST\" =~ (\^\S*) \]\]")


def _steps(workflow: dict) -> list[tuple[str, str, dict]]:
    """Yield (job name, step name, step) for every job step in the workflow."""
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            yield job_name, step.get("name", ""), step


def _snapshot(path: Path = APPROVED_SNAPSHOT):
    if not path.is_file():
        pytest.skip("approved release workflow snapshot is not present")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_tagless_dispatch_only_runs_release_please():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    decide = workflow.split("  decide:\n", 1)[1].split("  validate-release-version:\n", 1)[0]

    assert "inputs.tag_name != ''" in decide


@pytest.mark.parametrize("workflow_path", [APPROVED_SNAPSHOT])
def test_download_artifact_by_ids_uses_merge_multiple(workflow_path):
    """artifact-ids downloads land in a per-artifact subdirectory unless merge-multiple is set.

    actions/download-artifact@v4 flattens into `path` only when
    `isSingleArtifactDownload || inputs.mergeMultiple`; `artifact-ids` leaves
    `isSingleArtifactDownload` false, so without `merge-multiple: true` the
    distributions end up in `dist/<artifact-name>/` and the downstream
    `find <path> -maxdepth 1` counts evaluate to zero.
    """
    offenders = []
    for job_name, step_name, step in _steps(_snapshot(workflow_path)):
        if not str(step.get("uses", "")).startswith("actions/download-artifact@"):
            continue
        options = step.get("with") or {}
        if "artifact-ids" in options and options.get("merge-multiple") is not True:
            offenders.append(f"{job_name}/{step_name or '<unnamed>'}")

    assert not offenders, f"artifact-ids downloads missing merge-multiple: true: {sorted(offenders)}"


def test_artifact_digest_assertion_matches_bare_hex():
    """actions/upload-artifact@v4 emits `artifact-digest` as a bare 64-char hex digest.

    The `sha256:` prefix only appears in the internal finalize request, so a
    regular expression demanding that prefix can never match and aborts the
    job under `set -euo pipefail`.
    """
    matches = DIGEST_ASSERTION.findall(APPROVED_SNAPSHOT.read_text(encoding="utf-8"))
    assert matches, "no ARTIFACT_DIGEST assertion found in the approved snapshot"

    for pattern in matches:
        assert not pattern.startswith("^sha256:"), (
            f"ARTIFACT_DIGEST assertion {pattern!r} requires a 'sha256:' prefix "
            f"that upload-artifact never emits"
        )
        assert re.fullmatch(pattern, BARE_DIGEST), (
            f"ARTIFACT_DIGEST assertion {pattern!r} does not match a bare 64-char hex digest"
        )
