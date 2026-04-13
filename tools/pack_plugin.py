#!/usr/bin/env python3
"""Pack the dcc-mcp UXP plugin into a .ccx archive.

A .ccx file is a renamed ZIP archive containing the plugin files.
It can be installed via:
  - Creative Cloud Desktop App > Plugins > Manage Plugins > Install from file...
  - Photoshop > Plugins > Development > Load Plugin (during development)

Usage::

    python tools/pack_plugin.py                          # output to dist/plugin/
    python tools/pack_plugin.py --output /some/path      # custom output dir
    python tools/pack_plugin.py --version 0.2.0          # set version in manifest
    python tools/pack_plugin.py --help

The output file name follows the pattern::

    dcc-mcp-photoshop-bridge-<version>.ccx
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

# Files / directories to EXCLUDE from the .ccx archive
EXCLUDE_PATTERNS = [
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    "node_modules",
    ".git",
    ".gitignore",
    "*.md",       # README files are not needed at runtime
    "tests",
]

# Project root is two levels up from this script
_SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = _SCRIPT_DIR.parent
PLUGIN_DIR = PROJECT_ROOT / "bridge" / "uxp-plugin"


def _should_exclude(path: Path, plugin_root: Path) -> bool:
    """Return True if the path should be excluded from the archive."""
    rel = path.relative_to(plugin_root)
    for part in rel.parts:
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*"):
                if part.endswith(pattern[1:]):
                    return True
            elif part == pattern:
                return True
    return False


def _update_manifest_version(manifest_path: Path, version: str) -> dict:
    """Read manifest.json and return it with the version field updated."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["version"] = version
    return manifest


def pack_plugin(
    plugin_dir: Path,
    output_dir: Path,
    version: str,
) -> Path:
    """Pack the UXP plugin directory into a .ccx archive.

    Args:
        plugin_dir: Path to the ``bridge/uxp-plugin/`` directory.
        output_dir: Directory where the ``.ccx`` file will be written.
        version: Plugin version string (e.g. ``"0.1.0"``).

    Returns:
        Path to the created ``.ccx`` file.
    """
    if not plugin_dir.is_dir():
        print(f"ERROR: Plugin directory not found: {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest.json not found in {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    output_name = f"dcc-mcp-photoshop-bridge-{version}.ccx"
    output_path = output_dir / output_name

    # Update manifest version in memory
    manifest_data = _update_manifest_version(manifest_path, version)

    file_count = 0
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write manifest.json with updated version
        zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))
        file_count += 1

        # Walk the plugin directory and add all non-excluded files
        for file_path in sorted(plugin_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == "manifest.json":
                continue  # already written above
            if _should_exclude(file_path, plugin_dir):
                continue

            arcname = file_path.relative_to(plugin_dir).as_posix()
            zf.write(file_path, arcname)
            file_count += 1

    size_kb = output_path.stat().st_size / 1024
    print(f"Packed {file_count} files → {output_path}  ({size_kb:.1f} KB)")
    return output_path


def _read_version_from_manifest(plugin_dir: Path) -> str:
    """Read the version from manifest.json as a fallback."""
    try:
        with open(plugin_dir / "manifest.json", encoding="utf-8") as f:
            return json.load(f).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _read_version_from_pyproject(project_root: Path) -> str:
    """Read the version from pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    content = pyproject.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pack the dcc-mcp UXP plugin into a .ccx archive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=PLUGIN_DIR,
        help=f"Path to the UXP plugin directory (default: {PLUGIN_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "dist" / "plugin",
        help="Output directory for the .ccx file (default: dist/plugin/)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Plugin version (default: read from pyproject.toml)",
    )
    args = parser.parse_args()

    # Resolve version
    version = args.version
    if not version:
        version = _read_version_from_pyproject(PROJECT_ROOT)
    if not version:
        version = _read_version_from_manifest(args.plugin_dir)

    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+", version):
        print(
            f"WARNING: Version '{version}' does not look like semver. "
            "UXP manifest requires x.y.z format.",
            file=sys.stderr,
        )

    pack_plugin(
        plugin_dir=args.plugin_dir,
        output_dir=args.output,
        version=version,
    )


if __name__ == "__main__":
    main()
