#!/usr/bin/env python3
"""Build the dcc-mcp-photoshop standalone binary using PyOxidizer.

Output: dist/dcc-mcp-photoshop[.exe]  — single file, zero Python deps for end user.

Usage::

    python tools/build_binary.py
    python tools/build_binary.py --debug    # verbose build output for inspection

Prerequisites:
  - Python 3.8+
  - Rust toolchain (install from https://rustup.rs/)
  - PyOxidizer (``pip install pyoxidizer``)

The resulting binary can be:
  - Distributed with the Photoshop UXP plugin (.ccx)
  - Run directly by users: ./dcc-mcp-photoshop  or  dcc-mcp-photoshop.exe
  - Auto-launched by the UXP plugin on startup
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
BINARY_NAME = "dcc-mcp-photoshop"


def _check_pyoxidizer() -> None:
    """Verify PyOxidizer is installed and accessible."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pyoxidizer", "--version"],
            capture_output=True, check=True, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: PyOxidizer not found. Run: pip install pyoxidizer")
        sys.exit(1)


def _check_rust() -> None:
    """Verify the Rust toolchain is available (required by PyOxidizer)."""
    try:
        subprocess.run(["cargo", "--version"], capture_output=True, check=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "ERROR: Rust toolchain not found. "
            "Install from https://rustup.rs/ or run: rustup-init.exe",
        )
        sys.exit(1)


def _find_binary(build_dir: Path) -> Path | None:
    """Locate the built binary under *build_dir*.

    PyOxidizer places output in a platform/target-specific path like::

        build/<target-triple>/release/install/dcc-mcp-photoshop[.exe]

    This function searches the build tree for the binary by name.
    """
    matches = sorted(build_dir.rglob(BINARY_NAME + (".exe" if sys.platform == "win32" else "")))
    if matches:
        return matches[-1]  # Return the last match (deepest/most specific)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the dcc-mcp-photoshop standalone binary using PyOxidizer",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose build output for inspection",
    )
    args = parser.parse_args()

    # Check prerequisites
    _check_pyoxidizer()
    _check_rust()

    config = PROJECT_ROOT / "pyoxidizer.bzl"
    if not config.exists():
        print(f"ERROR: PyOxidizer config not found: {config}")
        sys.exit(1)

    output_dir = DIST_DIR / "binary"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building: {BINARY_NAME}")
    print(f"Config:   {config}")
    print(f"Output:   {output_dir}")
    print()

    cmd = [
        sys.executable, "-m", "pyoxidizer", "build",
        "--path", str(PROJECT_ROOT),
    ]

    if args.debug:
        cmd.append("--verbose")
        print(f"Command: {' '.join(cmd)}")
        print()

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"\nBuild FAILED (exit code {result.returncode})")
        sys.exit(result.returncode)

    # Locate the built binary
    pyoxidizer_build_dir = BUILD_DIR / "pyoxidizer"
    binary = _find_binary(pyoxidizer_build_dir) if pyoxidizer_build_dir.exists() else None

    if binary is None:
        for candidate in BUILD_DIR.iterdir():
            if candidate.is_dir() and candidate.name != "pyoxidizer":
                found = _find_binary(candidate)
                if found:
                    binary = found
                    break

    if binary is None or not binary.exists():
        print(
            f"\nERROR: Built binary not found in {BUILD_DIR}. "
            "Check build output above.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Copy binary to dist/binary/
    dest = output_dir / binary.name
    shutil.copy2(binary, dest)

    size_mb = dest.stat().st_size / 1_048_576
    print(f"\nBuild complete!")
    print(f"  Binary: {dest}  ({size_mb:.1f} MB)")
    print()
    print("Usage:")
    print(f"  {dest.name} --help")
    print(f"  {dest.name}                  # default ports (MCP:8765, WS:9001)")
    print(f"  {dest.name} --mcp-port 9000  # custom ports")


if __name__ == "__main__":
    main()
