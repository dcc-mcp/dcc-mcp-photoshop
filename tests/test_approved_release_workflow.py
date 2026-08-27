from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "scripts" / "ci" / "approved_release_workflow.yml"
DOWNLOAD_ARTIFACT_V8 = "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"
EXPECTED_RELEASE_ASSETS = {
    "dcc-mcp-photoshop-linux.tar.gz",
    "dcc-mcp-photoshop-macos.tar.gz",
    "dcc-mcp-photoshop-windows.tar.gz",
}
ATTACH_RELEASE_ASSETS_IF = (
    "always() && !cancelled() && "
    "needs.decide.result == 'success' && "
    "needs.validate-release-version.result == 'success' && "
    "needs.verify-release-source.result == 'success' && "
    "needs.bind-release-artifacts.result == 'success' && "
    "((github.ref_type == 'tag' && needs.publish.result == 'success') || "
    "(github.event_name == 'workflow_dispatch' && inputs.tag_name != '' && needs.publish.result == 'skipped'))"
)


def _workflow() -> dict:
    return yaml.safe_load(APPROVED.read_text(encoding="utf-8"))


def _download_steps(document: dict) -> list[dict]:
    return [
        step
        for job in document["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith("actions/download-artifact@")
    ]


def _step(job: dict, name: str) -> dict:
    return next(step for step in job["steps"] if step.get("name") == name)


def _attachment_gate_allows(event_name: str, ref_type: str, publish_result: str) -> bool:
    return (ref_type == "tag" and publish_result == "success") or (
        event_name == "workflow_dispatch" and publish_result == "skipped"
    )


def test_every_artifact_download_is_exact_v8_and_fails_on_digest_mismatch() -> None:
    downloads = _download_steps(_workflow())

    assert downloads
    assert {step["uses"] for step in downloads} == {DOWNLOAD_ARTIFACT_V8}
    for step in downloads:
        assert step["with"]["artifact-ids"]
        assert step["with"]["digest-mismatch"] == "error"
        assert "name" not in step["with"]


def test_release_bundle_binds_exact_run_artifacts_and_every_file_digest() -> None:
    document = _workflow()
    bind = document["jobs"]["bind-release-artifacts"]
    resolve = _step(bind, "Resolve exact build artifact identities")["run"]
    manifest = _step(bind, "Bind every release file to its SHA-256 digest")["run"]

    assert bind["permissions"] == {"actions": "read", "contents": "read"}
    assert "actions/runs/$GITHUB_RUN_ID/artifacts" in resolve
    assert ".workflow_run.head_sha" in resolve
    assert ".expired" in resolve
    assert ".digest" in resolve
    assert 'echo "${key}_id=$id"' in resolve
    assert "release-manifest.json" in manifest
    assert "sha256" in manifest
    assert "source_sha" in manifest
    assert "release_id" in manifest
    for name in EXPECTED_RELEASE_ASSETS:
        assert name in manifest


@pytest.mark.parametrize(
    ("event_name", "ref_type", "publish_result", "expected"),
    [
        ("push", "tag", "success", True),
        ("push", "tag", "failure", False),
        ("push", "tag", "cancelled", False),
        ("workflow_dispatch", "branch", "skipped", True),
        ("workflow_dispatch", "branch", "failure", False),
    ],
)
def test_asset_mutation_decision_table_requires_successful_tag_publisher(
    event_name: str,
    ref_type: str,
    publish_result: str,
    expected: bool,
) -> None:
    assert _attachment_gate_allows(event_name, ref_type, publish_result) is expected

    attach = _workflow()["jobs"]["attach-release-assets"]
    assert "publish" in attach["needs"]
    condition = attach["if"]
    assert condition == ATTACH_RELEASE_ASSETS_IF
    assert "needs.publish.result == 'success'" in condition
    assert "needs.publish.result == 'skipped'" in condition
    assert "!cancelled()" in condition


def test_every_external_mutation_recaptures_exact_tag_source_and_release_state() -> None:
    jobs = _workflow()["jobs"]
    publish = jobs["publish"]
    attach = jobs["attach-release-assets"]
    publish_step = next(index for index, step in enumerate(publish["steps"]) if "pypi-publish@" in step.get("uses", ""))
    recapture = publish["steps"][publish_step - 1]
    upload = _step(attach, "Attach exact assets without clobbering")["run"]

    assert recapture["name"] == "Recapture exact tag source and release state"
    for token in ("RELEASE_ID", "RELEASE_CREATED_AT", "RELEASE_PUBLISHED_AT", "RELEASE_DRAFT", "RELEASE_PRERELEASE"):
        assert token in recapture["run"]
        assert token in upload
    assert "for asset in" in upload
    assert "recapture_release" in upload
    assert "uploads.github.com" in upload
    assert "--clobber" not in upload


def test_release_jobs_keep_write_permissions_at_the_mutation_boundary() -> None:
    document = _workflow()
    jobs = document["jobs"]

    assert document["permissions"] == {}
    assert jobs["publish"]["permissions"] == {"actions": "read", "contents": "read", "id-token": "write"}
    assert jobs["attach-release-assets"]["permissions"] == {
        "actions": "read",
        "contents": "write",
    }
    for name, job in jobs.items():
        if name not in {"release-please", "publish", "attach-release-assets"}:
            assert all(value != "write" for value in job.get("permissions", {}).values())


def test_manifest_and_publisher_scripts_bind_the_real_release_file_names(tmp_path: Path) -> None:
    document = _workflow()
    bind = document["jobs"]["bind-release-artifacts"]
    publish = document["jobs"]["publish"]
    assets = tmp_path / "release-assets"
    assets.mkdir()
    names = {
        "dcc_mcp_photoshop-1.2.3-py3-none-any.whl",
        "dcc_mcp_photoshop-1.2.3.tar.gz",
        *EXPECTED_RELEASE_ASSETS,
    }
    for index, name in enumerate(sorted(names), start=1):
        (assets / name).write_bytes(f"artifact-{index}".encode())
    environment = {
        **os.environ,
        "TAG_NAME": "v1.2.3",
        "VERIFIED_SOURCE_SHA": "a" * 40,
        "RELEASE_ID": "123",
        **{
            f"{platform}_{field}".upper(): value
            for platform in ("python", "windows", "linux", "macos")
            for field, value in (("id", "123"), ("digest", f"sha256:{'b' * 64}"))
        },
    }

    manifest_result = subprocess.run(
        [sys.executable, "-c", _step(bind, "Bind every release file to its SHA-256 digest")["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert manifest_result.returncode == 0, manifest_result.stdout + manifest_result.stderr
    manifest = json.loads((tmp_path / "release-manifest.json").read_text(encoding="utf-8"))
    assert {entry["name"] for entry in manifest["files"]} == names
    assert set(manifest["source_artifacts"]) == {"python", "windows", "linux", "macos"}
    assert all(
        identity == {"id": 123, "digest": f"sha256:{'b' * 64}"} for identity in manifest["source_artifacts"].values()
    )

    bundle = tmp_path / "release-bundle"
    bundle.mkdir()
    for source in assets.iterdir():
        (bundle / source.name).write_bytes(source.read_bytes())
    (bundle / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    publish_result = subprocess.run(
        [sys.executable, "-c", _step(publish, "Verify exact per-file release manifest")["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert publish_result.returncode == 0, publish_result.stdout + publish_result.stderr
    assert {path.name for path in (tmp_path / "dist").iterdir()} == {
        "dcc_mcp_photoshop-1.2.3-py3-none-any.whl",
        "dcc_mcp_photoshop-1.2.3.tar.gz",
    }
