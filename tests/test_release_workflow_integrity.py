"""Tests for the release workflow digest drift check.

The release workflow carries PyPI Trusted Publishing credentials, so the check
that binds it to a snapshot has to fail closed: every test here either proves a
real change is caught or that a cosmetic one is not, and none of them may pass
by asserting nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.ci.check_release_workflow_digest import (
    APPROVED_SNAPSHOT,
    RELEASE_WORKFLOW,
    DriftError,
    main,
    release_workflow_digest,
)

MINIMAL_WORKFLOW = """name: Release

on:
  push:
    branches: [main]

permissions: {}

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - run: echo publish
"""

# Same document as MINIMAL_WORKFLOW, different bytes: key order, comments,
# blank lines, CRLF endings and quoting style all differ.
COSMETIC_VARIANT = (
    "# leading comment\r\n"
    "\r\n"
    "name: Release\r\n"
    "permissions: {}\r\n"
    "jobs:\r\n"
    "  publish:\r\n"
    "    steps:\n"
    "      # a comment inside the step\n"
    "      - run: echo publish\n"
    "\n"
    "    permissions:\n"
    "      id-token: write\n"
    "    runs-on: ubuntu-latest\r\n"
    "on:\r\n"
    "  push:\r\n"
    "    branches: ['main']\r\n"
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _run(monkeypatch, capsys, workflow: Path, snapshot: Path, *extra: str):
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_release_workflow_digest", "--workflow", str(workflow), "--snapshot", str(snapshot), *extra],
    )
    code = main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_committed_release_workflow_matches_the_approved_snapshot(monkeypatch, capsys):
    code, out, err = _run(monkeypatch, capsys, RELEASE_WORKFLOW, APPROVED_SNAPSHOT)

    assert code == 0, err
    assert "integrity ok" in out


def test_snapshot_digest_equals_release_workflow_digest():
    # The invariant the CI job enforces, asserted directly so a broken argparse
    # path cannot hide a drifting snapshot.
    assert release_workflow_digest(RELEASE_WORKFLOW) == release_workflow_digest(APPROVED_SNAPSHOT)


def test_structural_drift_is_detected(tmp_path, monkeypatch, capsys):
    snapshot = _write(tmp_path / "approved.yml", MINIMAL_WORKFLOW)
    drifted = _write(
        tmp_path / "release.yml", MINIMAL_WORKFLOW.replace("permissions: {}", "permissions:\n  contents: write")
    )

    code, out, err = _run(monkeypatch, capsys, drifted, snapshot)

    assert code == 1
    assert "drifted" in err
    assert release_workflow_digest(snapshot) in err
    assert release_workflow_digest(drifted) in err
    assert out == ""


def test_dropping_a_publish_step_is_detected(tmp_path, monkeypatch, capsys):
    snapshot = _write(tmp_path / "approved.yml", MINIMAL_WORKFLOW)
    drifted = _write(tmp_path / "release.yml", MINIMAL_WORKFLOW.replace("      - run: echo publish\n", ""))

    code, _, err = _run(monkeypatch, capsys, drifted, snapshot)

    assert code == 1
    assert "drifted" in err


def test_cosmetic_edits_do_not_move_the_digest(tmp_path):
    original = _write(tmp_path / "original.yml", MINIMAL_WORKFLOW)
    cosmetic = _write(tmp_path / "cosmetic.yml", COSMETIC_VARIANT)

    assert original.read_bytes() != cosmetic.read_bytes()
    assert release_workflow_digest(original) == release_workflow_digest(cosmetic)


def test_cosmetic_drift_does_not_fail_the_check(tmp_path, monkeypatch, capsys):
    snapshot = _write(tmp_path / "approved.yml", MINIMAL_WORKFLOW)
    cosmetic = _write(tmp_path / "release.yml", COSMETIC_VARIANT)

    code, out, err = _run(monkeypatch, capsys, cosmetic, snapshot)

    assert code == 0, err
    assert "integrity ok" in out


def test_missing_snapshot_fails_closed(tmp_path, monkeypatch, capsys):
    workflow = _write(tmp_path / "release.yml", MINIMAL_WORKFLOW)

    code, _, err = _run(monkeypatch, capsys, workflow, tmp_path / "does-not-exist.yml")

    assert code == 1
    assert "unavailable" in err
    assert "does-not-exist.yml" in err


def test_missing_workflow_fails_closed(tmp_path, monkeypatch, capsys):
    snapshot = _write(tmp_path / "approved.yml", MINIMAL_WORKFLOW)

    code, _, err = _run(monkeypatch, capsys, tmp_path / "does-not-exist.yml", snapshot)

    assert code == 1
    assert "unavailable" in err


def test_yaml_aliases_are_rejected(tmp_path):
    aliased = _write(
        tmp_path / "aliased.yml",
        "name: Release\npermissions: &perms\n  contents: write\njobs:\n  publish:\n    permissions: *perms\n",
    )

    with pytest.raises(DriftError, match="aliases"):
        release_workflow_digest(aliased)


def test_duplicate_mapping_keys_are_rejected(tmp_path):
    duplicated = _write(
        tmp_path / "duplicated.yml",
        "name: Release\nname: Release Again\npermissions: {}\n",
    )

    with pytest.raises(DriftError, match="duplicate"):
        release_workflow_digest(duplicated)


def test_unsupported_value_types_are_rejected(tmp_path):
    # An unquoted ISO date parses as a datetime.date, which the canonical form
    # refuses rather than silently serialising in a PyYAML-specific way.
    dated = _write(tmp_path / "dated.yml", "name: Release\ncreated: 2026-09-26\n")

    with pytest.raises(DriftError, match="unsupported value type"):
        release_workflow_digest(dated)


def test_update_snapshot_refreshes_the_record(tmp_path, monkeypatch, capsys):
    workflow = _write(tmp_path / "release.yml", MINIMAL_WORKFLOW)
    snapshot = tmp_path / "approved.yml"

    code, out, _ = _run(monkeypatch, capsys, workflow, snapshot, "--update-snapshot")
    assert code == 0
    assert snapshot.is_file()
    assert release_workflow_digest(snapshot) in out

    code, out, err = _run(monkeypatch, capsys, workflow, snapshot)
    assert code == 0, err

    _write(workflow, MINIMAL_WORKFLOW.replace("permissions: {}", "permissions:\n  contents: write"))
    code, _, err = _run(monkeypatch, capsys, workflow, snapshot)
    assert code == 1
    assert "drifted" in err


def test_print_digest_emits_the_canonical_digest(tmp_path, monkeypatch, capsys):
    workflow = _write(tmp_path / "release.yml", MINIMAL_WORKFLOW)

    code, out, _ = _run(monkeypatch, capsys, workflow, tmp_path / "unused.yml", "--print-digest")

    assert code == 0
    assert out.strip() == release_workflow_digest(workflow)
    assert len(out.strip()) == 64
