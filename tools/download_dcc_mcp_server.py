#!/usr/bin/env python3
"""Download the dcc-mcp-server binary from dcc-mcp-core GitHub Releases.

The binary is platform-specific and is downloaded from:
  https://github.com/dcc-mcp/dcc-mcp-core/releases/download/v{version}/dcc-mcp-server-{platform-spec}

Usage::

    python tools/download_dcc_mcp_server.py                              # auto-detect platform + version
    python tools/download_dcc_mcp_server.py --platform windows            # download Windows binary (e.g. from CI)
    python tools/download_dcc_mcp_server.py --version 0.18.15             # specific version
    python tools/download_dcc_mcp_server.py --output path/to/dir          # custom output directory
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "bin"

# The dcc-mcp-core repo where server binaries are published
CORE_REPO = "dcc-mcp/dcc-mcp-core"
RELEASE_BASE = f"https://github.com/{CORE_REPO}/releases/download"

# Platform → (asset_name_suffix, local_output_name)
_PLATFORM_MAP = {
    "windows": ("windows-x86_64.exe", ".exe"),
    "linux": ("linux-x86_64", ""),
    "macos": ("macos-universal2", ""),
}


def _detect_platform() -> str:
    """Auto-detect the current platform key."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "linux":
        return "linux"
    elif sys.platform == "darwin":
        return "macos"
    else:
        print(f"ERROR: unsupported platform: {sys.platform}", file=sys.stderr)
        sys.exit(1)


def _read_core_version_from_package() -> str | None:
    """Read dcc-mcp-core version from the installed Python package."""
    try:
        import dcc_mcp_core  # type: ignore[import-untyped]

        return getattr(dcc_mcp_core, "__version__", None)
    except ImportError:
        return None


def _read_core_version_from_pyproject(pyproject: Path) -> str | None:
    """Parse the dcc-mcp-core version constraint from pyproject.toml.

    Returns the minimum version from the constraint (e.g. ``>=0.18.14`` → ``0.18.14``).
    """
    if not pyproject.exists():
        return None
    content = pyproject.read_text(encoding="utf-8")
    m = re.search(r"dcc-mcp-core\s*>=\s*([\d.]+)", content)
    if m:
        return m.group(1)
    return None


def _resolve_version(version_arg: str | None) -> str:
    """Resolve which version of dcc-mcp-server to download."""
    if version_arg:
        return version_arg

    # 1. Try the installed Python package
    pkg_ver = _read_core_version_from_package()
    if pkg_ver:
        print(f"Using dcc-mcp-core v{pkg_ver} from installed package")
        return pkg_ver

    # 2. Fall back to pyproject.toml minimum version
    pyproject = PROJECT_ROOT / "pyproject.toml"
    pyproject_ver = _read_core_version_from_pyproject(pyproject)
    if pyproject_ver:
        print(f"Using dcc-mcp-core v{pyproject_ver} from pyproject.toml (minimum)")
        return pyproject_ver

    print(
        "ERROR: cannot determine dcc-mcp-core version. Install dcc-mcp-core or pass --version.",
        file=sys.stderr,
    )
    sys.exit(1)


def _platform_spec(platform_key: str) -> tuple[str, str]:
    """Return (asset_name_suffix, local_extension) for the given platform."""
    spec = _PLATFORM_MAP.get(platform_key)
    if spec is None:
        valid = ", ".join(_PLATFORM_MAP)
        print(
            f"ERROR: unknown platform '{platform_key}'. Valid: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)
    return spec


def download_server(
    version: str,
    platform_key: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Download dcc-mcp-server for *platform_key* (or current platform).

    Returns the path to the downloaded binary.
    """
    if platform_key is None:
        platform_key = _detect_platform()

    asset_suffix, local_ext = _platform_spec(platform_key)
    asset_name = f"dcc-mcp-server-{asset_suffix}"
    local_name = f"dcc-mcp-server{local_ext}"
    url = f"{RELEASE_BASE}/v{version}/{asset_name}"
    output_path = output_dir / local_name

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading dcc-mcp-server v{version} for {platform_key}...")
    print(f"  URL: {url}")
    print(f"  → {output_path}")

    try:
        urllib.request.urlretrieve(url, output_path)
    except urllib.error.HTTPError as e:
        print(f"ERROR: download failed (HTTP {e.code}): {url}", file=sys.stderr)
        print(
            f"  Check that dcc-mcp-core v{version} exists at https://github.com/{CORE_REPO}/releases",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: download failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # Basic sanity: the binary should be > 1 MB
    size_bytes = output_path.stat().st_size
    if size_bytes < 1_000_000:
        print(
            f"WARNING: downloaded file is very small ({size_bytes / 1024:.1f} KB), may not be a valid binary",
            file=sys.stderr,
        )

    # Make executable on non-Windows
    if platform_key != "windows":
        output_path.chmod(output_path.stat().st_mode | 0o111)

    size_mb = size_bytes / 1_048_576
    print(f"Downloaded: {output_path}  ({size_mb:.1f} MB)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download dcc-mcp-server binary from dcc-mcp-core releases",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="dcc-mcp-core version to download (default: from installed package)",
    )
    parser.add_argument(
        "--platform",
        choices=list(_PLATFORM_MAP),
        default=None,
        help="Target platform (default: auto-detect from current OS)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    version = _resolve_version(args.version)
    download_server(version, platform_key=args.platform, output_dir=args.output)

    # Append version metadata for other tools to read
    meta_path = args.output / ".dcc-mcp-server-version"
    meta_path.write_text(version, encoding="utf-8")
    print(f"Version metadata: {meta_path}")


if __name__ == "__main__":
    main()
