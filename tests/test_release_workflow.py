from __future__ import annotations

import re
from pathlib import Path

import yaml

# The release workflow is the single source of truth for the publish path now
# that the trusted-release-policy snapshot and its checker have been dropped.
RELEASE_WORKFLOW = Path(".github/workflows/release.yml")

# actions/upload-artifact@v4 exposes `artifact-digest` as a bare lowercase
# sha256 hex digest (src/shared/upload-artifact.ts:22 -> @actions/artifact
# lib/internal/upload/blob-upload.js:77-88).
#
# Mind the prefix asymmetry: the server-side artifact metadata and the
# `Expected Digest` line printed by the download log DO carry a `sha256:`
# prefix, but the `steps.*.outputs.artifact-digest` step output consumed here
# does NOT. An assertion demanding the prefix on the step output can therefore
# never match, and aborts the job under `set -euo pipefail`.
#
# Captured from a real attach-release-assets run (run 36175991243) rather than
# a synthetic filler, so the fixture reflects a digest a run actually produced.
REAL_DIGEST = "4da0ee69d11cbdc0dd818ea966624333a86b7534cbff8db021b6907187db0ca7"
# Complements the real value by mixing digits and a-f letters throughout, so a
# pattern that only happened to match one sample cannot pass unnoticed.
MIXED_DIGEST = "1f2e3d4c5b6a798807162534435261708f9eadbc0123456789abcdef01234567"

VALID_DIGESTS = [REAL_DIGEST, MIXED_DIGEST]

# Rejected shapes: wrong length either side of 64, a non-hex letter, the wrong
# case, and the `sha256:` prefix that only other surfaces carry.
INVALID_DIGESTS = {
    "63 chars": "a" * 63,
    "65 chars": "a" * 65,
    "contains g": "g" * 64,
    "uppercase": "A" * 64,
    "sha256 prefix": "sha256:" + "a" * 64,
}

DIGEST_ASSERTION = re.compile(r'\[\[ "\$ARTIFACT_DIGEST" =~ (\^\S*) \]\]')


def _steps(workflow: dict) -> list[tuple[str, str, dict]]:
    """Return (job name, step name, step) for every job step in the workflow."""
    steps = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            steps.append((job_name, step.get("name", ""), step))
    return steps


def _release_workflow(path: Path = RELEASE_WORKFLOW) -> dict:
    # Deliberately not pytest.skip: a missing workflow must fail loudly rather
    # than report a green run that asserted nothing.
    assert path.is_file(), f"missing release workflow at {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_tagless_dispatch_only_runs_release_please():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    decide = workflow.split("  decide:\n", 1)[1].split("  validate-release-version:\n", 1)[0]

    assert "inputs.tag_name != ''" in decide


def test_download_artifact_by_ids_uses_merge_multiple():
    """`artifact-ids` downloads must set `merge-multiple: true`.

    actions/download-artifact@v4 flattens the download into `path` only when
    `isSingleArtifactDownload || inputs.mergeMultiple`
    (src/download-artifact.ts:47 and :177). `artifact-ids` leaves
    `isSingleArtifactDownload` false, so without `merge-multiple: true` the
    distributions land in `dist/<artifact-name>/` and every downstream
    `find <path> -maxdepth 1` count evaluates to zero.
    """
    offenders = []
    checked = 0
    for job_name, step_name, step in _steps(_release_workflow()):
        if not str(step.get("uses", "")).startswith("actions/download-artifact@"):
            continue
        options = step.get("with") or {}
        if "artifact-ids" not in options:
            continue
        checked += 1
        if options.get("merge-multiple") is not True:
            offenders.append(f"{job_name}/{step_name or '<unnamed>'}")

    assert checked, "no artifact-ids download step found; this assertion no longer covers anything"
    assert not offenders, "artifact-ids downloads missing merge-multiple: true: " + ", ".join(sorted(offenders))


def test_artifact_digest_assertion_matches_bare_hex():
    """The ARTIFACT_DIGEST assertions must accept a bare 64-char hex digest."""
    patterns = DIGEST_ASSERTION.findall(RELEASE_WORKFLOW.read_text(encoding="utf-8"))

    assert patterns, "no ARTIFACT_DIGEST assertion found in the release workflow"
    assert len(patterns) >= 2, f"expected at least 2 ARTIFACT_DIGEST assertions, found {len(patterns)}"

    for pattern in patterns:
        assert not pattern.startswith("^sha256:"), (
            f"ARTIFACT_DIGEST assertion {pattern!r} requires a 'sha256:' prefix "
            "that the artifact-digest step output never carries"
        )
        for digest in VALID_DIGESTS:
            assert re.fullmatch(pattern, digest), (
                f"ARTIFACT_DIGEST assertion {pattern!r} does not match the bare hex digest {digest}"
            )
        for label, digest in INVALID_DIGESTS.items():
            assert re.fullmatch(pattern, digest) is None, (
                f"ARTIFACT_DIGEST assertion {pattern!r} wrongly accepts {label}: {digest}"
            )
