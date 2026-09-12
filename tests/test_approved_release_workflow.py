from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile
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
STANDALONE_BINARY_NAMES = {
    "dcc-mcp-photoshop-linux.tar.gz": "dcc-mcp-photoshop",
    "dcc-mcp-photoshop-macos.tar.gz": "dcc-mcp-photoshop",
    "dcc-mcp-photoshop-windows.tar.gz": "dcc-mcp-photoshop.exe",
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


def _bash() -> str:
    executable = shutil.which("bash")
    if executable and Path(executable).name.lower() == "bash.exe" and "system32" not in executable.lower():
        return executable
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        return str(git_bash)
    if executable:
        return executable
    pytest.skip("bash is required to execute the approved release state gates")


def _run_release_state_gate(run: str, tmp_path: Path, *, mutation_marker: str) -> subprocess.CompletedProcess[str]:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'case "$*" in\n'
        '  *git/ref/tags/*) printf \'%s\\n\' \'{"object":{"type":"commit","sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}\' ;;\n'
        '  *releases/tags/*) printf \'%s\\n\' \'{"id":123,"tag_name":"v1.2.3","target_commitish":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","created_at":"2026-08-27T00:00:00Z","published_at":"2026-08-27T00:01:00Z","draft":false,"prerelease":false,"immutable":true}\' ;;\n'
        '  *--method\\ POST*) : > "$MUTATION_MARKER"; exit 1 ;;\n'
        "  *releases/123/assets*) printf '\\n' ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    script = tmp_path / "gate.sh"
    script.write_text(run, encoding="utf-8")
    script.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "dcc-mcp/dcc-mcp-photoshop",
        "TAG_NAME": "v1.2.3",
        "VERIFIED_SOURCE_SHA": "a" * 40,
        "RELEASE_ID": "123",
        "RELEASE_CREATED_AT": "2026-08-27T00:00:00Z",
        "RELEASE_PUBLISHED_AT": "2026-08-27T00:01:00Z",
        "RELEASE_DRAFT": "false",
        "RELEASE_PRERELEASE": "false",
        "RELEASE_IMMUTABLE": "false",
        "MUTATION_MARKER": mutation_marker,
    }
    return subprocess.run(
        [_bash(), script.name],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _package_metadata(name: str, version: str) -> bytes:
    return f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\n".encode()


def _write_wheel(
    path: Path,
    *,
    metadata_name: str,
    metadata_version: str,
    dist_info_version: str | None = None,
) -> None:
    dist_info = f"dcc_mcp_photoshop-{dist_info_version or metadata_version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{dist_info}/METADATA", _package_metadata(metadata_name, metadata_version))


def _write_sdist(path: Path, *, metadata_name: str, metadata_version: str) -> None:
    root = path.name[: -len(".tar.gz")]
    metadata = _package_metadata(metadata_name, metadata_version)
    info = tarfile.TarInfo(f"{root}/PKG-INFO")
    info.size = len(metadata)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(metadata))


def _write_standalone(path: Path, binary_name: str, binary: bytes = b"standalone-binary") -> None:
    info = tarfile.TarInfo(binary_name)
    info.mode = 0o755
    info.size = len(binary)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(binary))


def _append_wheel_member(path: Path, name: str, content: bytes = b"hostile") -> None:
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(name, content)


def _append_wheel_backslash_member(path: Path) -> None:
    canonical = b"folder/escape.txt"
    hostile = b"folder\\escape.txt"
    _append_wheel_member(path, canonical.decode())
    raw = path.read_bytes()
    assert raw.count(canonical) == 2
    path.write_bytes(raw.replace(canonical, hostile))


def _append_wheel_nul_member(path: Path) -> None:
    canonical = b"badXname.txt"
    hostile = b"bad\x00name.txt"
    _append_wheel_member(path, canonical.decode())
    raw = path.read_bytes()
    assert raw.count(canonical) == 2
    path.write_bytes(raw.replace(canonical, hostile))


def _append_wheel_with_divergent_local_name(path: Path) -> None:
    central_name = b"safe-entry.txt"
    local_name = b"../../evil.txt"
    assert len(central_name) == len(local_name)
    _append_wheel_member(path, central_name.decode())
    raw = path.read_bytes()
    assert raw.count(central_name) == 2
    path.write_bytes(raw.replace(central_name, local_name, 1))


def _mutate_first_zip_local_field(path: Path, offset: int, value: int, field_format: str) -> None:
    raw = bytearray(path.read_bytes())
    local_header = raw.index(b"PK\x03\x04")
    struct.pack_into(field_format, raw, local_header + offset, value)
    path.write_bytes(raw)


def _toggle_first_zip_local_flags(path: Path, mask: int) -> None:
    raw = bytearray(path.read_bytes())
    local_header = raw.index(b"PK\x03\x04")
    flags = struct.unpack_from("<H", raw, local_header + 6)[0]
    struct.pack_into("<H", raw, local_header + 6, flags ^ mask)
    path.write_bytes(raw)


class _UnseekableBuffer(io.BytesIO):
    def seekable(self) -> bool:
        return False

    def seek(self, *args: object, **kwargs: object) -> int:
        raise OSError("seek disabled")


def _write_wheel_with_data_descriptor(path: Path) -> None:
    buffer = _UnseekableBuffer()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "dcc_mcp_photoshop-1.2.3.dist-info/METADATA",
            _package_metadata("dcc-mcp-photoshop", "1.2.3"),
        )
    path.write_bytes(buffer.getvalue())


def _mutate_first_zip_descriptor_field(path: Path, offset: int, value: int) -> None:
    raw = bytearray(path.read_bytes())
    descriptor = raw.index(b"PK\x07\x08")
    struct.pack_into("<I", raw, descriptor + offset, value)
    path.write_bytes(raw)


def _write_archive_validator(tmp_path: Path) -> Path:
    bind = _workflow()["jobs"]["bind-release-artifacts"]
    result = subprocess.run(
        [sys.executable, "-c", _step(bind, "Write shared fail-closed archive validator")["run"]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path / "policy" / "archive_validator.py"


def _append_sdist_member(path: Path, member: tarfile.TarInfo, content: bytes = b"") -> None:
    existing: list[tuple[tarfile.TarInfo, bytes]] = []
    with tarfile.open(path, "r:gz") as archive:
        for current in archive.getmembers():
            extracted = archive.extractfile(current) if current.isfile() else None
            existing.append((current, extracted.read() if extracted is not None else b""))
    with tarfile.open(path, "w:gz") as archive:
        for current, raw in existing:
            archive.addfile(current, io.BytesIO(raw) if current.isfile() else None)
        member.size = len(content) if member.isfile() else 0
        archive.addfile(member, io.BytesIO(content) if member.isfile() else None)


def _write_sdist_with_raw_pax_escape(path: Path) -> None:
    root = "dcc_mcp_photoshop-1.2.3"
    metadata = _package_metadata("dcc-mcp-photoshop", "1.2.3")
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        metadata_info = tarfile.TarInfo(f"{root}/PKG-INFO")
        metadata_info.size = len(metadata)
        archive.addfile(metadata_info, io.BytesIO(metadata))
        hostile = tarfile.TarInfo("../../raw-escape")
        hostile.pax_headers = {"path": f"{root}/safe.txt"}
        hostile.size = len(b"hostile")
        archive.addfile(hostile, io.BytesIO(b"hostile"))


def _write_sdist_with_pax_link_escape(path: Path) -> None:
    root = "dcc_mcp_photoshop-1.2.3"
    metadata = _package_metadata("dcc-mcp-photoshop", "1.2.3")
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        metadata_info = tarfile.TarInfo(f"{root}/PKG-INFO")
        metadata_info.size = len(metadata)
        archive.addfile(metadata_info, io.BytesIO(metadata))
        member = tarfile.TarInfo(f"{root}/safe.txt")
        member.pax_headers = {"linkpath": "../../pax-link-escape"}
        member.size = len(b"safe")
        archive.addfile(member, io.BytesIO(b"safe"))


def _write_sdist_with_gnu_longlink_escape(path: Path) -> None:
    root = "dcc_mcp_photoshop-1.2.3"
    metadata = _package_metadata("dcc-mcp-photoshop", "1.2.3")
    with tarfile.open(path, "w:gz", format=tarfile.GNU_FORMAT) as archive:
        metadata_info = tarfile.TarInfo(f"{root}/PKG-INFO")
        metadata_info.size = len(metadata)
        archive.addfile(metadata_info, io.BytesIO(metadata))
        member = tarfile.TarInfo(f"{root}/unsafe-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../" * 40 + "outside"
        archive.addfile(member)


def _write_sdist_with_global_pax_link_escape(path: Path) -> None:
    root = "dcc_mcp_photoshop-1.2.3"
    metadata = _package_metadata("dcc-mcp-photoshop", "1.2.3")
    with tarfile.open(
        path,
        "w:gz",
        format=tarfile.PAX_FORMAT,
        pax_headers={"linkpath": "../../global-pax-link-escape"},
    ) as archive:
        metadata_info = tarfile.TarInfo(f"{root}/PKG-INFO")
        metadata_info.size = len(metadata)
        archive.addfile(metadata_info, io.BytesIO(metadata))


def _write_sdist_with_safe_gnu_longname(path: Path) -> None:
    root = "dcc_mcp_photoshop-1.2.3"
    metadata = _package_metadata("dcc-mcp-photoshop", "1.2.3")
    with tarfile.open(path, "w:gz", format=tarfile.GNU_FORMAT) as archive:
        metadata_info = tarfile.TarInfo(f"{root}/PKG-INFO")
        metadata_info.size = len(metadata)
        archive.addfile(metadata_info, io.BytesIO(metadata))
        member = tarfile.TarInfo(f"{root}/{'safe' * 30}.txt")
        member.size = len(b"safe")
        archive.addfile(member, io.BytesIO(b"safe"))


def _make_wheel_metadata_a_symlink(path: Path) -> None:
    members: list[tuple[zipfile.ZipInfo, bytes]] = []
    with zipfile.ZipFile(path) as archive:
        for current in archive.infolist():
            members.append((current, archive.read(current)))
    with zipfile.ZipFile(path, "w") as archive:
        for current, raw in members:
            if current.filename.endswith(".dist-info/METADATA"):
                current.create_system = 3
                current.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(current, raw)


def _apply_archive_attack(assets: Path, attack: str) -> Path:
    wheel = assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl"
    sdist = assets / "dcc_mcp_photoshop-1.2.3.tar.gz"
    if attack == "wheel traversal":
        _append_wheel_member(wheel, "../../outside.txt")
        return wheel
    if attack == "sdist second root":
        info = tarfile.TarInfo("other-1.0/PKG-INFO")
        _append_sdist_member(sdist, info, _package_metadata("dcc-mcp-photoshop", "1.2.3"))
        return sdist
    if attack == "wheel metadata symlink":
        _make_wheel_metadata_a_symlink(wheel)
        return wheel
    if attack == "wheel shadow metadata":
        _append_wheel_member(
            wheel,
            "other-1.0.dist-info/METADATA",
            _package_metadata("dcc-mcp-photoshop", "1.2.3"),
        )
        return wheel
    if attack == "wheel casefold shadow metadata":
        _append_wheel_member(
            wheel,
            "other-9.9.9.DIST-INFO/METADATA",
            _package_metadata("dcc-mcp-photoshop", "1.2.3"),
        )
        return wheel
    if attack == "wheel divergent local name":
        _append_wheel_with_divergent_local_name(wheel)
        return wheel
    if attack == "wheel local method mismatch":
        _mutate_first_zip_local_field(wheel, 8, zipfile.ZIP_DEFLATED, "<H")
        return wheel
    if attack == "wheel local flags mismatch":
        _toggle_first_zip_local_flags(wheel, 0x800)
        return wheel
    if attack == "wheel local crc mismatch":
        _mutate_first_zip_local_field(wheel, 14, 0, "<I")
        return wheel
    if attack == "wheel local compressed size mismatch":
        _mutate_first_zip_local_field(wheel, 18, 1, "<I")
        return wheel
    if attack == "wheel local uncompressed size mismatch":
        _mutate_first_zip_local_field(wheel, 22, 1, "<I")
        return wheel
    if attack == "wheel descriptor crc mismatch":
        _write_wheel_with_data_descriptor(wheel)
        _mutate_first_zip_descriptor_field(wheel, 4, 0)
        return wheel
    if attack == "wheel descriptor compressed size mismatch":
        _write_wheel_with_data_descriptor(wheel)
        _mutate_first_zip_descriptor_field(wheel, 8, 1)
        return wheel
    if attack == "wheel descriptor uncompressed size mismatch":
        _write_wheel_with_data_descriptor(wheel)
        _mutate_first_zip_descriptor_field(wheel, 12, 1)
        return wheel
    if attack == "wheel descriptor local placeholder mismatch":
        _write_wheel_with_data_descriptor(wheel)
        _mutate_first_zip_local_field(wheel, 14, 1, "<I")
        return wheel
    if attack == "wheel alternate data stream":
        _append_wheel_member(wheel, "dcc_mcp_photoshop/module.py:stream")
        return wheel
    if attack == "wheel excessive path depth":
        _append_wheel_member(wheel, "/".join(["part"] * 300))
        return wheel
    if attack == "wheel excessive segment length":
        _append_wheel_member(wheel, "a" * 256)
        return wheel
    if attack == "wheel excessive total path length":
        _append_wheel_member(wheel, "/".join(["a" * 20] * 60))
        return wheel
    if attack == "wheel reserved device name":
        _append_wheel_member(wheel, "dcc_mcp_photoshop/CON.txt")
        return wheel
    if attack == "wheel trailing dot component":
        _append_wheel_member(wheel, "dcc_mcp_photoshop/module.")
        return wheel
    if attack == "wheel trailing space component":
        _append_wheel_member(wheel, "dcc_mcp_photoshop/module ")
        return wheel
    if attack == "wheel nul member":
        _append_wheel_nul_member(wheel)
        return wheel
    if attack == "sdist raw pax traversal":
        _write_sdist_with_raw_pax_escape(sdist)
        return sdist
    if attack == "sdist pax link traversal":
        _write_sdist_with_pax_link_escape(sdist)
        return sdist
    if attack == "sdist gnu longlink traversal":
        _write_sdist_with_gnu_longlink_escape(sdist)
        return sdist
    if attack == "sdist global pax link traversal":
        _write_sdist_with_global_pax_link_escape(sdist)
        return sdist
    if attack == "sdist alternate data stream":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/module.py:stream")
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist excessive path depth":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/" + "/".join(["part"] * 300))
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist excessive segment length":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/" + "a" * 256)
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist excessive total path length":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/" + "/".join(["a" * 20] * 60))
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist reserved device name":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/AUX.txt")
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist trailing dot component":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/module.")
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist trailing space component":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/module ")
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist nul member":
        member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/safe\x00escape")
        _append_sdist_member(sdist, member, b"hostile")
        return sdist
    if attack == "sdist duplicate normalized member":
        lower = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/package.txt")
        _append_sdist_member(sdist, lower, b"first")
        upper = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/PACKAGE.TXT")
        _append_sdist_member(sdist, upper, b"second")
        return sdist
    if attack == "standalone linux traversal":
        standalone = assets / "dcc-mcp-photoshop-linux.tar.gz"
        member = tarfile.TarInfo("../../outside.txt")
        _append_sdist_member(standalone, member, b"hostile")
        return standalone
    if attack == "standalone linux symlink":
        standalone = assets / "dcc-mcp-photoshop-linux.tar.gz"
        member = tarfile.TarInfo("unsafe-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../outside.txt"
        _append_sdist_member(standalone, member)
        return standalone
    if attack == "standalone windows wrong binary layout":
        standalone = assets / "dcc-mcp-photoshop-windows.tar.gz"
        _write_standalone(standalone, "dcc-mcp-photoshop")
        return standalone
    if attack == "standalone macos compression bomb":
        standalone = assets / "dcc-mcp-photoshop-macos.tar.gz"
        _write_standalone(standalone, "dcc-mcp-photoshop", b"0" * (1024 * 1024))
        return standalone
    if attack == "standalone windows truncated gzip":
        standalone = assets / "dcc-mcp-photoshop-windows.tar.gz"
        standalone.write_bytes(standalone.read_bytes()[:-8])
        return standalone
    raise AssertionError(f"unknown attack: {attack}")


def _refresh_manifest_entry(bundle: Path, changed: Path) -> None:
    manifest_path = bundle / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed_entry = next(entry for entry in manifest["files"] if entry["name"] == changed.name)
    changed_entry["size"] = changed.stat().st_size
    changed_entry["sha256"] = hashlib.sha256(changed.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _release_environment() -> dict[str, str]:
    return {
        **os.environ,
        "TAG_NAME": "v1.2.3",
        "VERSION": "1.2.3",
        "VERIFIED_SOURCE_SHA": "a" * 40,
        "RELEASE_ID": "123",
        **{
            f"{platform}_{field}".upper(): value
            for platform in ("python", "windows", "linux", "macos")
            for field, value in (("id", "123"), ("digest", f"sha256:{'b' * 64}"))
        },
    }


def _run_manifest_builder(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    bind = _workflow()["jobs"]["bind-release-artifacts"]
    _write_archive_validator(tmp_path)
    return subprocess.run(
        [sys.executable, "-c", _step(bind, "Bind every release file to its SHA-256 digest")["run"]],
        cwd=tmp_path,
        env=_release_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def _run_publisher_preflight(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    publish = _workflow()["jobs"]["publish"]
    source_policy = tmp_path / "policy"
    bundle_policy = tmp_path / "release-bundle" / "policy"
    if source_policy.is_dir() and not bundle_policy.exists():
        shutil.copytree(source_policy, bundle_policy)
    return subprocess.run(
        [sys.executable, "-c", _step(publish, "Verify exact per-file release manifest")["run"]],
        cwd=tmp_path,
        env=_release_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def _write_release_assets(
    root: Path,
    *,
    wheel_metadata_name: str = "dcc-mcp-photoshop",
    wheel_metadata_version: str = "1.2.3",
    sdist_metadata_name: str = "dcc-mcp-photoshop",
    sdist_metadata_version: str = "1.2.3",
) -> None:
    root.mkdir()
    _write_wheel(
        root / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl",
        metadata_name=wheel_metadata_name,
        metadata_version=wheel_metadata_version,
        dist_info_version="1.2.3",
    )
    _write_sdist(
        root / "dcc_mcp_photoshop-1.2.3.tar.gz",
        metadata_name=sdist_metadata_name,
        metadata_version=sdist_metadata_version,
    )
    for name, binary_name in STANDALONE_BINARY_NAMES.items():
        _write_standalone(root / name, binary_name)


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


def test_standalone_packaging_selects_only_the_matrix_binary() -> None:
    package = _step(_workflow()["jobs"]["build-binary"], "Package standalone archive")["run"]

    assert '"${{ matrix.binary_name }}"' in package
    assert "dist/binary -czf" in package
    assert not package.rstrip().endswith(" .")


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
    for token in (
        "RELEASE_ID",
        "RELEASE_CREATED_AT",
        "RELEASE_PUBLISHED_AT",
        "RELEASE_DRAFT",
        "RELEASE_PRERELEASE",
        "RELEASE_IMMUTABLE",
    ):
        assert token in recapture["run"]
        assert token in upload
    assert "for asset in" in upload
    assert "recapture_release" in upload
    assert "uploads.github.com" in upload
    assert "--clobber" not in upload


def test_immutable_release_drift_stops_before_publisher_and_asset_mutation(tmp_path: Path) -> None:
    jobs = _workflow()["jobs"]
    source = jobs["verify-release-source"]
    publish = jobs["publish"]
    attach = jobs["attach-release-assets"]
    publisher_marker = tmp_path / "publisher-mutated"
    asset_marker = tmp_path / "asset-mutated"

    assert source["outputs"]["release_immutable"] == "${{ steps.source.outputs.release_immutable }}"
    assert "RELEASE_IMMUTABLE=$(jq -r '.immutable' <<< \"$RELEASE\")" in source["steps"][1]["run"]
    assert 'test "$RELEASE_IMMUTABLE" = "false"' in source["steps"][1]["run"]
    assert 'echo "release_immutable=$RELEASE_IMMUTABLE" >> "$GITHUB_OUTPUT"' in source["steps"][1]["run"]

    publish_gate = _step(publish, "Recapture exact tag source and release state")
    publish_result = _run_release_state_gate(
        publish_gate["run"],
        tmp_path,
        mutation_marker=str(asset_marker),
    )
    if publish_result.returncode == 0:
        publisher_marker.touch()
    assert publish_gate["env"]["RELEASE_IMMUTABLE"] == "${{ needs.verify-release-source.outputs.release_immutable }}"
    assert publish_result.returncode != 0
    assert not publisher_marker.exists()

    bundle = tmp_path / "release-bundle"
    bundle.mkdir()
    (bundle / "dcc-mcp-photoshop-linux.tar.gz").write_bytes(b"asset")
    attach_gate = _step(attach, "Attach exact assets without clobbering")
    attach_result = _run_release_state_gate(
        attach_gate["run"],
        tmp_path,
        mutation_marker=str(asset_marker),
    )
    assert attach_gate["env"]["RELEASE_IMMUTABLE"] == "${{ needs.verify-release-source.outputs.release_immutable }}"
    assert attach_result.returncode != 0
    assert not asset_marker.exists()


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


def test_manifest_rejects_a_wheel_for_another_project_and_version(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    assets.mkdir()
    _write_wheel(
        assets / "other_project-9.9.9-py3-none-any.whl",
        metadata_name="other-project",
        metadata_version="9.9.9",
    )
    _write_sdist(
        assets / "dcc_mcp_photoshop-1.2.3.tar.gz",
        metadata_name="dcc-mcp-photoshop",
        metadata_version="1.2.3",
    )
    for name, binary_name in STANDALONE_BINARY_NAMES.items():
        _write_standalone(assets / name, binary_name)

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


@pytest.mark.parametrize(
    "attack",
    [
        "wheel traversal",
        "sdist second root",
        "wheel metadata symlink",
        "wheel shadow metadata",
        "wheel casefold shadow metadata",
        "wheel divergent local name",
        "wheel local method mismatch",
        "wheel local flags mismatch",
        "wheel local crc mismatch",
        "wheel local compressed size mismatch",
        "wheel local uncompressed size mismatch",
        "wheel descriptor crc mismatch",
        "wheel descriptor compressed size mismatch",
        "wheel descriptor uncompressed size mismatch",
        "wheel descriptor local placeholder mismatch",
        "wheel alternate data stream",
        "wheel excessive path depth",
        "wheel excessive segment length",
        "wheel excessive total path length",
        "wheel reserved device name",
        "wheel trailing dot component",
        "wheel trailing space component",
        "wheel nul member",
        "sdist raw pax traversal",
        "sdist pax link traversal",
        "sdist gnu longlink traversal",
        "sdist global pax link traversal",
        "sdist alternate data stream",
        "sdist excessive path depth",
        "sdist excessive segment length",
        "sdist excessive total path length",
        "sdist reserved device name",
        "sdist trailing dot component",
        "sdist trailing space component",
        "sdist nul member",
        "sdist duplicate normalized member",
        "standalone linux traversal",
        "standalone linux symlink",
        "standalone windows wrong binary layout",
        "standalone macos compression bomb",
        "standalone windows truncated gzip",
    ],
)
def test_manifest_rejects_adversarial_archive_members(tmp_path: Path, attack: str) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    _apply_archive_attack(assets, attack)

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_builder_and_publisher_accept_safe_gnu_longname_records(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    _write_sdist_with_safe_gnu_longname(assets / "dcc_mcp_photoshop-1.2.3.tar.gz")

    manifest_result = _run_manifest_builder(tmp_path)
    assert manifest_result.returncode == 0, manifest_result.stdout + manifest_result.stderr
    bundle = tmp_path / "release-bundle"
    shutil.copytree(assets, bundle)
    shutil.copy2(tmp_path / "release-manifest.json", bundle / "release-manifest.json")

    publisher_result = _run_publisher_preflight(tmp_path)

    assert publisher_result.returncode == 0, publisher_result.stdout + publisher_result.stderr


def test_builder_and_publisher_accept_consistent_zip_data_descriptor_records(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    _write_wheel_with_data_descriptor(assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl")

    manifest_result = _run_manifest_builder(tmp_path)
    assert manifest_result.returncode == 0, manifest_result.stdout + manifest_result.stderr
    bundle = tmp_path / "release-bundle"
    shutil.copytree(assets, bundle)
    shutil.copy2(tmp_path / "release-manifest.json", bundle / "release-manifest.json")

    publisher_result = _run_publisher_preflight(tmp_path)

    assert publisher_result.returncode == 0, publisher_result.stdout + publisher_result.stderr


@pytest.mark.parametrize(
    "member_name",
    [
        "/absolute.txt",
        "//server/share.txt",
        "C:/escape.txt",
        "folder\\escape.txt",
        "bad\x01name",
        "bad\u0085name",
        "a/../b",
        "fullwidth\uff0fslash",
    ],
)
def test_manifest_rejects_unsafe_wheel_member_paths(tmp_path: Path, member_name: str) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    wheel = assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl"
    if "\\" in member_name:
        _append_wheel_backslash_member(wheel)
    else:
        _append_wheel_member(wheel, member_name)

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_manifest_rejects_duplicate_normalized_wheel_members(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    _append_wheel_member(
        assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl",
        "DCC_MCP_PHOTOSHOP-1.2.3.DIST-INFO/metadata",
        _package_metadata("dcc-mcp-photoshop", "1.2.3"),
    )

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0


@pytest.mark.parametrize(
    "member_type",
    [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE],
)
def test_manifest_rejects_non_regular_sdist_members(tmp_path: Path, member_type: bytes) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    member = tarfile.TarInfo("dcc_mcp_photoshop-1.2.3/unsafe")
    member.type = member_type
    member.linkname = "dcc_mcp_photoshop-1.2.3/PKG-INFO"
    _append_sdist_member(assets / "dcc_mcp_photoshop-1.2.3.tar.gz", member)

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0


def test_manifest_rejects_wheel_compression_bomb_ratio(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    wheel = assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dcc_mcp_photoshop/payload.bin", b"0" * (1024 * 1024))

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0


def test_manifest_rejects_excessive_wheel_member_count(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    wheel = assets / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a") as archive:
        for index in range(4096):
            archive.writestr(f"dcc_mcp_photoshop/data/{index}", b"")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0


@pytest.mark.parametrize("invalid_name", ["bad\x00name", "bad\udcffname"])
def test_shared_validator_rejects_nul_and_malformed_member_encoding(tmp_path: Path, invalid_name: str) -> None:
    validator_path = _write_archive_validator(tmp_path)
    spec = importlib.util.spec_from_file_location("archive_validator", validator_path)
    assert spec is not None and spec.loader is not None
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    with pytest.raises((AssertionError, UnicodeEncodeError)):
        validator._member_path(invalid_name, set())


def test_shared_validator_refuses_optimized_python(tmp_path: Path) -> None:
    validator_path = _write_archive_validator(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-O",
            "-c",
            "import runpy; runpy.run_path(__import__('sys').argv[1])",
            str(validator_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "optimized Python" in result.stderr


def test_builder_and_publisher_use_the_bundled_shared_validator() -> None:
    document = _workflow()
    bind = document["jobs"]["bind-release-artifacts"]
    publish = document["jobs"]["publish"]
    builder = _step(bind, "Bind every release file to its SHA-256 digest")["run"]
    preflight = _step(publish, "Verify exact per-file release manifest")["run"]
    upload = _step(bind, "Upload exact release bundle")["with"]["path"]
    validator = _step(bind, "Write shared fail-closed archive validator")["run"]

    assert "def validate_release_distributions" in validator
    assert "MAX_MEMBERS = 4096" in validator
    assert "MAX_MEMBER_SIZE = 64 * 1024 * 1024" in validator
    assert "MAX_TOTAL_SIZE = 256 * 1024 * 1024" in validator
    assert "MAX_COMPRESSION_RATIO = 200" in validator
    assert "MAX_PATH_DEPTH = 64" in validator
    assert "MAX_PATH_BYTES = 1024" in validator
    assert "MAX_PATH_SEGMENT_BYTES = 255" in validator
    assert "def _validate_zip_records" in validator
    assert "def _validate_raw_tar" in validator
    assert "def _validate_standalone" in validator
    assert "def _validate_pax_paths" in validator
    assert "archive validator refuses optimized Python" in validator
    assert "from archive_validator import validate_release_distributions" in builder
    assert "from archive_validator import validate_release_distributions" in preflight
    assert "policy/archive_validator.py" in upload


@pytest.mark.parametrize(
    "attack",
    [
        "wheel traversal",
        "sdist second root",
        "wheel metadata symlink",
        "wheel shadow metadata",
        "wheel casefold shadow metadata",
        "wheel divergent local name",
        "wheel local method mismatch",
        "wheel local flags mismatch",
        "wheel local crc mismatch",
        "wheel local compressed size mismatch",
        "wheel local uncompressed size mismatch",
        "wheel descriptor crc mismatch",
        "wheel descriptor compressed size mismatch",
        "wheel descriptor uncompressed size mismatch",
        "wheel descriptor local placeholder mismatch",
        "wheel alternate data stream",
        "wheel excessive path depth",
        "wheel excessive segment length",
        "wheel excessive total path length",
        "wheel reserved device name",
        "wheel trailing dot component",
        "wheel trailing space component",
        "wheel nul member",
        "sdist raw pax traversal",
        "sdist pax link traversal",
        "sdist gnu longlink traversal",
        "sdist global pax link traversal",
        "sdist alternate data stream",
        "sdist excessive path depth",
        "sdist excessive segment length",
        "sdist excessive total path length",
        "sdist reserved device name",
        "sdist trailing dot component",
        "sdist trailing space component",
        "sdist nul member",
        "sdist duplicate normalized member",
        "standalone linux traversal",
        "standalone linux symlink",
        "standalone windows wrong binary layout",
        "standalone macos compression bomb",
        "standalone windows truncated gzip",
    ],
)
def test_publisher_rejects_self_consistent_adversarial_archive_members(tmp_path: Path, attack: str) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    manifest_result = _run_manifest_builder(tmp_path)
    assert manifest_result.returncode == 0, manifest_result.stdout + manifest_result.stderr
    bundle = tmp_path / "release-bundle"
    shutil.copytree(assets, bundle)
    shutil.copy2(tmp_path / "release-manifest.json", bundle / "release-manifest.json")
    changed = _apply_archive_attack(bundle, attack)
    _refresh_manifest_entry(bundle, changed)

    result = _run_publisher_preflight(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "dist").exists()


def test_manifest_rejects_an_sdist_with_the_wrong_filename_identity(tmp_path: Path) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    (assets / "dcc_mcp_photoshop-1.2.3.tar.gz").rename(assets / "other_project-9.9.9.tar.gz")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_manifest_rejects_wrong_wheel_internal_project_metadata(tmp_path: Path) -> None:
    _write_release_assets(tmp_path / "release-assets", wheel_metadata_name="other-project")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_manifest_rejects_wrong_wheel_internal_version_metadata(tmp_path: Path) -> None:
    _write_release_assets(tmp_path / "release-assets", wheel_metadata_version="9.9.9")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_manifest_rejects_wrong_sdist_internal_project_metadata(tmp_path: Path) -> None:
    _write_release_assets(tmp_path / "release-assets", sdist_metadata_name="other-project")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


def test_manifest_rejects_wrong_sdist_internal_version_metadata(tmp_path: Path) -> None:
    _write_release_assets(tmp_path / "release-assets", sdist_metadata_version="9.9.9")

    result = _run_manifest_builder(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "release-manifest.json").exists()


@pytest.mark.parametrize("distribution", ["wheel", "sdist"])
def test_publisher_preflight_rejects_semantically_wrong_distribution(
    tmp_path: Path,
    distribution: str,
) -> None:
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    manifest_result = _run_manifest_builder(tmp_path)
    assert manifest_result.returncode == 0, manifest_result.stdout + manifest_result.stderr
    manifest = json.loads((tmp_path / "release-manifest.json").read_text(encoding="utf-8"))
    bundle = tmp_path / "release-bundle"
    shutil.copytree(assets, bundle)
    if distribution == "wheel":
        changed = bundle / "dcc_mcp_photoshop-1.2.3-py3-none-any.whl"
        _write_wheel(
            changed,
            metadata_name="other-project",
            metadata_version="1.2.3",
            dist_info_version="1.2.3",
        )
    else:
        changed = bundle / "dcc_mcp_photoshop-1.2.3.tar.gz"
        _write_sdist(changed, metadata_name="other-project", metadata_version="1.2.3")
    changed_entry = next(entry for entry in manifest["files"] if entry["name"] == changed.name)
    changed_entry["size"] = changed.stat().st_size
    changed_entry["sha256"] = hashlib.sha256(changed.read_bytes()).hexdigest()
    (bundle / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_publisher_preflight(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "dist").exists()


def test_manifest_and_publisher_scripts_bind_the_real_release_file_names(tmp_path: Path) -> None:
    document = _workflow()
    publish = document["jobs"]["publish"]
    assets = tmp_path / "release-assets"
    _write_release_assets(assets)
    names = {
        "dcc_mcp_photoshop-1.2.3-py3-none-any.whl",
        "dcc_mcp_photoshop-1.2.3.tar.gz",
        *EXPECTED_RELEASE_ASSETS,
    }
    environment = _release_environment()

    manifest_result = _run_manifest_builder(tmp_path)
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
    shutil.copytree(tmp_path / "policy", bundle / "policy")
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
