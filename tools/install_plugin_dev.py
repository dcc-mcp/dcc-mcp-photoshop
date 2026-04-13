#!/usr/bin/env python3
"""Install the dcc-mcp UXP plugin for development via junction/symlink.

Windows:  %APPDATA%\\Adobe\\UXP\\Plugins\\External\\com.dcc-mcp.photoshop-bridge
macOS:    ~/Library/Application Support/Adobe/UXP/Plugins/External/com.dcc-mcp.photoshop-bridge

This is the path UXP reads for user-installed external plugins.
(NOT PluginsStorage which is for per-plugin data.)

Usage:
    python tools/install_plugin_dev.py
    python tools/install_plugin_dev.py --uninstall
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ID = "com.dcc-mcp.photoshop-bridge"
_PROJECT_ROOT = Path(__file__).parent.parent
PLUGIN_SRC = _PROJECT_ROOT / "bridge" / "uxp-plugin"


def _get_install_dir() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Adobe" / "UXP" / "Plugins" / "External"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Adobe" / "UXP" / "Plugins" / "External"
    else:
        print("Linux is not supported by Adobe Photoshop", file=sys.stderr)
        sys.exit(1)


def install() -> None:
    install_dir = _get_install_dir()
    dst = install_dir / PLUGIN_ID
    src = PLUGIN_SRC.resolve()

    if not src.exists():
        print(f"ERROR: Plugin source not found: {src}", file=sys.stderr)
        sys.exit(1)

    install_dir.mkdir(parents=True, exist_ok=True)

    # Remove existing junction/symlink if present
    if dst.exists() or dst.is_symlink():
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", f"rmdir \"{dst}\""], check=True)
        else:
            dst.unlink()
        print(f"Removed existing: {dst}")

    # Create junction (Windows) or symlink (macOS)
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", f'mklink /J "{dst}" "{src}"'],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout.strip())
    else:
        dst.symlink_to(src)
        print(f"Symlink created: {dst} -> {src}")

    print(f"\nPlugin installed to: {dst}")
    print("Restart Photoshop to load the plugin.")
    print(f"\nVerify: ls \"{install_dir}\"")


def uninstall() -> None:
    dst = _get_install_dir() / PLUGIN_ID
    if dst.exists() or dst.is_symlink():
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", f"rmdir \"{dst}\""], check=True)
        else:
            dst.unlink()
        print(f"Removed: {dst}")
    else:
        print(f"Not installed: {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install/uninstall dcc-mcp UXP plugin for development")
    parser.add_argument("--uninstall", action="store_true", help="Remove the junction/symlink")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
    else:
        install()


if __name__ == "__main__":
    main()
