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

The resulting binary runs as the adapter process beside the independently
distributed adobepy broker and bridge.
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
            ["pyoxidizer", "--version"],
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


def _copy_runtime_dlls(src_dir: Path, dst_dir: Path) -> None:
    """Copy runtime DLLs (python*.dll, vcruntime*.dll) alongside the binary.

    PyOxidizer shared builds on Windows place python3.dll, python*.dll, and
    VC++ redist DLLs next to the binary.  Copy them so the binary can be run
    from the output directory without requiring those paths in PATH.
    """
    if sys.platform != "win32":
        return
    for dll in src_dir.glob("*.dll"):
        shutil.copy2(dll, dst_dir / dll.name)


def _copy_lib_dir(src_dir: Path, dst_dir: Path) -> None:
    """Copy the lib/ directory containing Python stdlib and site-packages.

    PyOxidizer places all Python resources (stdlib, dependencies, our package)
    into a lib/ subdirectory next to the binary.  The binary's sys.path is
    configured to look at ``$ORIGIN/lib``.
    """
    src_lib = src_dir / "lib"
    dst_lib = dst_dir / "lib"
    if src_lib.is_dir():
        if dst_lib.exists():
            shutil.rmtree(dst_lib)
        shutil.copytree(src_lib, dst_lib, ignore=shutil.ignore_patterns("__pycache__"))


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
        "pyoxidizer", "build",
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

    # Copy runtime DLLs and Python stdlib/site-packages lib/ directory.
    _copy_runtime_dlls(binary.parent, output_dir)
    _copy_lib_dir(binary.parent, output_dir)

    size_mb = dest.stat().st_size / 1_048_576
    print("\nBuild complete!")
    print(f"  Binary: {dest}  ({size_mb:.1f} MB)")
    if sys.platform == "win32":
        dlls = list(output_dir.glob("*.dll"))
        if dlls:
            dll_size = sum(f.stat().st_size for f in dlls) / 1_048_576
            print(f"  Runtime DLLs ({len(dlls)} files, {dll_size:.1f} MB total)")
        lib_dir = output_dir / "lib"
        if lib_dir.is_dir():
            lib_size = sum(f.stat().st_size for f in lib_dir.rglob("*") if f.is_file()) / 1_048_576
            print(f"  Python lib  : {lib_dir}  ({lib_size:.1f} MB)")
    print()
    print("Usage:")
    print(f"  {dest.name} --help")
    print(f"  {dest.name}                  # OS-assigned MCP port; broker 127.0.0.1:47391")
    print(f"  {dest.name} --mcp-port 9000  # custom ports")


if __name__ == "__main__":
    main()
