#!/usr/bin/env python3
"""Stage the local sidecar server into the UXP plugin source tree.

This is for development-link installs where Photoshop reads directly from
bridge/uxp-plugin instead of an unpacked .ccx.

If the sidecar binary is not found at the default path, this script
will automatically download it from dcc-mcp-core GitHub Releases.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

from download_dcc_mcp_server import _resolve_version, download_server
from pack_plugin import _hidden_vbs_launcher, _sidecar_launcher, _sidecar_stopper

PROJECT_ROOT = Path(__file__).parent.parent
PLUGIN_DIR = PROJECT_ROOT / "bridge" / "uxp-plugin"
BIN_DIR = PROJECT_ROOT / "bin"
SKILLS_DIR = PROJECT_ROOT / "src" / "dcc_mcp_photoshop" / "skills"
SIDECAR_DIR = PLUGIN_DIR / "sidecar"
WINDOWS_DIR = SIDECAR_DIR / "windows"


def _binary_name() -> str:
    """Return the binary name for the host platform."""
    return "dcc-mcp-server.exe" if sys.platform == "win32" else "dcc-mcp-server"


def _default_binary_path() -> Path:
    return BIN_DIR / _binary_name()


def _auto_download_binary(platform_key: str | None) -> Path:
    """Download dcc-mcp-server if missing."""
    version = _resolve_version(None)
    return download_server(
        version=version,
        platform_key=platform_key,
        output_dir=BIN_DIR,
    )


def stage(binary: Path | None = None, platform: str | None = None) -> None:
    if binary is None:
        binary = _default_binary_path()
        if not binary.is_file():
            print(f"Sidecar binary not found at {binary}, downloading automatically...")
            binary = _auto_download_binary(platform)
    binary = binary.resolve()
    if not binary.is_file():
        print(f"ERROR: sidecar binary not found: {binary}", file=sys.stderr)
        sys.exit(1)

    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)
    dst = WINDOWS_DIR / binary.name
    if dst.exists() and filecmp.cmp(binary, dst, shallow=False):
        print(f"Sidecar binary already current: {dst}")
    else:
        shutil.copy2(binary, dst)
    (WINDOWS_DIR / "start-sidecar.cmd").write_text(
        _sidecar_launcher(binary.name),
        encoding="utf-8",
    )
    (WINDOWS_DIR / "start-sidecar.vbs").write_text(
        _hidden_vbs_launcher("start-sidecar.cmd"),
        encoding="utf-8",
    )
    (WINDOWS_DIR / "stop-sidecar.cmd").write_text(
        _sidecar_stopper(binary.name),
        encoding="utf-8",
    )
    (WINDOWS_DIR / "stop-sidecar.vbs").write_text(
        _hidden_vbs_launcher("stop-sidecar.cmd"),
        encoding="utf-8",
    )
    skills_dst = SIDECAR_DIR / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    shutil.copytree(
        SKILLS_DIR,
        skills_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    print(f"Staged sidecar binary: {dst}")
    print(f"Staged sidecar launcher: {WINDOWS_DIR / 'start-sidecar.cmd'}")
    print(f"Staged hidden launcher: {WINDOWS_DIR / 'start-sidecar.vbs'}")
    print(f"Staged sidecar stopper: {WINDOWS_DIR / 'stop-sidecar.cmd'}")
    print(f"Staged hidden stopper: {WINDOWS_DIR / 'stop-sidecar.vbs'}")
    print(f"Staged Photoshop skills: {skills_dst}")


def clean() -> None:
    if SIDECAR_DIR.exists():
        shutil.rmtree(SIDECAR_DIR)
        print(f"Removed staged sidecar: {SIDECAR_DIR}")
    else:
        print(f"No staged sidecar: {SIDECAR_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage/clean UXP plugin sidecar files")
    parser.add_argument(
        "--binary", type=Path, default=None, help=f"Path to server binary (default: bin/{_binary_name()})"
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos"],
        default=None,
        help="Target platform for auto-download (default: host OS)",
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        stage(binary=args.binary, platform=args.platform)


if __name__ == "__main__":
    main()
