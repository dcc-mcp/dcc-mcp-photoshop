"""Regression coverage for install-receipt path identity comparisons."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dcc_mcp_photoshop.install_verification import _canonical_device_path, _same_path

_DEVICE_PREFIX = "\\\\?\\"
_DEVICE_EXECUTABLE = _DEVICE_PREFIX + r"C:\Program Files\adobepy\bin\adobepy.exe"
_PLAIN_EXECUTABLE = r"C:\Program Files\adobepy\bin\adobepy.exe"


def test_canonical_device_path_strips_extended_length_prefix() -> None:
    assert _canonical_device_path(_DEVICE_EXECUTABLE) == _PLAIN_EXECUTABLE


def test_canonical_device_path_translates_unc_prefix() -> None:
    assert _canonical_device_path(r"\\?\UNC\host\share\adobepy.exe") == r"\\host\share\adobepy.exe"


def test_canonical_device_path_leaves_ordinary_paths_unchanged() -> None:
    for value in (_PLAIN_EXECUTABLE, "/opt/adobepy/adobepy.exe", "relative/adobepy.exe"):
        assert _canonical_device_path(value) == value


def test_canonical_device_path_ignores_a_prefix_without_a_drive_absolute_path() -> None:
    # An unrelated string must not be rewritten into a plausible path match.
    assert _canonical_device_path(r"\\?\relative\adobepy.exe") == r"\\?\relative\adobepy.exe"


def test_same_path_matches_identical_real_files(tmp_path: Path) -> None:
    executable = tmp_path / "adobepy.exe"
    executable.write_bytes(b"")
    assert _same_path(str(executable), str(executable.resolve())) is True


def test_same_path_still_rejects_a_different_file(tmp_path: Path) -> None:
    selected = tmp_path / "adobepy.exe"
    selected.write_bytes(b"")
    other = tmp_path / "other.exe"
    other.write_bytes(b"")
    assert _same_path(str(selected), str(other)) is False


@pytest.mark.skipif(os.name != "nt", reason="extended-length path resolution is Windows-specific")
def test_same_path_matches_broker_device_path_with_receipt_path(tmp_path: Path) -> None:
    executable = tmp_path / "adobepy.exe"
    executable.write_bytes(b"")
    ordinary = str(executable.resolve())
    device = _DEVICE_PREFIX + ordinary

    assert _same_path(device, ordinary) is True
    assert _same_path(ordinary, device) is True


@pytest.mark.skipif(os.name != "nt", reason="extended-length path resolution is Windows-specific")
def test_same_path_rejects_different_executables_both_with_device_prefix(tmp_path: Path) -> None:
    selected = tmp_path / "adobepy.exe"
    selected.write_bytes(b"")
    other = tmp_path / "other.exe"
    other.write_bytes(b"")

    assert _same_path(_DEVICE_PREFIX + str(selected.resolve()), _DEVICE_PREFIX + str(other.resolve())) is False
