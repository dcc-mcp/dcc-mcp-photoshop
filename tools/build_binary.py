#!/usr/bin/env python3
"""Build the dcc-mcp-photoshop standalone binary using PyInstaller.

Output: dist/dcc-mcp-photoshop[.exe]  — single file, zero Python deps for end user.

Usage:
    python tools/build_binary.py
    python tools/build_binary.py --onedir   # directory mode (faster startup)
    python tools/build_binary.py --debug    # keep temp files for inspection

The resulting binary can be:
  - Distributed with the Photoshop UXP plugin (.ccx)
  - Run directly by users: ./dcc-mcp-photoshop  or  dcc-mcp-photoshop.exe
  - Auto-launched by the UXP plugin on startup
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
DIST_DIR = PROJECT_ROOT / "dist"
BINARY_NAME = "dcc-mcp-photoshop"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dcc-mcp-photoshop standalone binary")
    parser.add_argument("--onedir", action="store_true",
                        help="Build as directory (faster startup) instead of single file")
    parser.add_argument("--debug", action="store_true",
                        help="Keep temp files for inspection")
    parser.add_argument("--upx", action="store_true",
                        help="Compress binary with UPX (requires UPX installed)")
    args = parser.parse_args()

    # Ensure PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("ERROR: PyInstaller not found. Run: pip install pyinstaller")
        sys.exit(1)

    entry_point = SRC_ROOT / "dcc_mcp_photoshop" / "cli.py"
    if not entry_point.exists():
        print(f"ERROR: Entry point not found: {entry_point}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", BINARY_NAME,
        "--distpath", str(DIST_DIR / "binary"),
        "--workpath", str(PROJECT_ROOT / "build" / "pyinstaller"),
        "--specpath", str(PROJECT_ROOT / "build"),
        "--paths", str(SRC_ROOT),
        # Include the built-in skills directory
        "--add-data", f"{SRC_ROOT / 'dcc_mcp_photoshop' / 'skills'}{_sep()}dcc_mcp_photoshop/skills",
        "--hidden-import", "dcc_mcp_photoshop",
        "--hidden-import", "dcc_mcp_photoshop.server",
        "--hidden-import", "dcc_mcp_photoshop.bridge",
        "--hidden-import", "dcc_mcp_photoshop.api",
        "--hidden-import", "dcc_mcp_photoshop.capabilities",
        "--hidden-import", "dcc_mcp_core",
        "--hidden-import", "websockets",
        "--hidden-import", "websockets.asyncio",
        "--hidden-import", "websockets.asyncio.server",
        "--collect-all", "dcc_mcp_core",
        "--collect-all", "websockets",
    ]

    if args.onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    if not args.debug:
        cmd.append("--clean")

    if not args.upx:
        cmd.append("--noupx")

    # Add console (keep terminal open to see logs)
    cmd.append("--console")

    cmd.append(str(entry_point))

    print(f"Building: {BINARY_NAME}")
    print(f"Mode: {'directory' if args.onedir else 'single file'}")
    print(f"Output: {DIST_DIR / 'binary'}")
    print()

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"\nBuild FAILED (exit code {result.returncode})")
        sys.exit(result.returncode)

    binary = DIST_DIR / "binary" / BINARY_NAME
    if sys.platform == "win32":
        binary = binary.with_suffix(".exe")
        if not binary.exists():
            binary = DIST_DIR / "binary" / BINARY_NAME / f"{BINARY_NAME}.exe"

    print(f"\nBuild complete!")
    if binary.exists():
        size_mb = binary.stat().st_size / 1_048_576
        print(f"  Binary: {binary}  ({size_mb:.1f} MB)")
    print()
    print("Usage:")
    print(f"  {binary.name} --help")
    print(f"  {binary.name}                  # default ports (MCP:8765, WS:9001)")
    print(f"  {binary.name} --mcp-port 9000  # custom ports")


def _sep() -> str:
    """PyInstaller --add-data separator: ';' on Windows, ':' on Unix."""
    return ";" if sys.platform == "win32" else ":"


if __name__ == "__main__":
    main()
