"""Install the UXP .ccx plugin into Adobe Photoshop."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

from dcc_mcp_core.skill import skill_entry


def _get_uxp_plugin_dir() -> str:
    """Get the UXP plugins directory for the current platform."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "Adobe", "UXP", "Plugins", "External")
    elif system == "Darwin":
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support", "Adobe", "UXP", "Plugins", "External")
    else:
        return ""


def _find_ccx_files(search_dir: str) -> list[str]:
    """Find .ccx files in the given directory."""
    matches = []
    for root, _dirs, files in os.walk(search_dir):
        for f in files:
            if f.endswith(".ccx"):
                matches.append(os.path.join(root, f))
    return matches


def _download_ccx(version: str, dest_dir: str) -> str | None:
    """Download a .ccx from GitHub Releases."""
    ver = version or "latest"
    # Use gh CLI if available, otherwise construct URL
    try:
        if version:
            url = (
                f"https://github.com/dcc-mcp/dcc-mcp-photoshop/releases/download/"
                f"v{version}/dcc-mcp-photoshop-bridge-{version}.ccx"
            )
        else:
            url = (
                "https://github.com/dcc-mcp/dcc-mcp-photoshop/releases/latest/download/"
                "dcc-mcp-photoshop-bridge.ccx"
            )

        dest_path = os.path.join(dest_dir, f"dcc-mcp-photoshop-bridge-{ver}.ccx")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps", "--dest", dest_dir, url],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Fallback: try curl
        if not os.path.isfile(dest_path):
            curl_result = subprocess.run(
                ["curl", "-L", "-o", dest_path, url],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if curl_result.returncode == 0 and os.path.isfile(dest_path):
                return dest_path
        elif os.path.isfile(dest_path):
            return dest_path
    except Exception:
        pass
    return None


def _generate_guide(version: str) -> str:
    """Generate step-by-step installation guide for the UXP plugin."""
    ver = version or "latest"
    system = platform.system()
    uxp_dir = _get_uxp_plugin_dir()
    lines = [
        "# UXP Plugin Installation Guide",
        "",
        f"## 1. Download the .ccx file (v{ver})",
        "",
    ]

    if system == "Windows":
        lines.extend([
            "   a. Visit: https://github.com/dcc-mcp/dcc-mcp-photoshop/releases",
            f"   b. Download: dcc-mcp-photoshop-bridge-{ver}.ccx",
            "",
            "## 2. Install via Creative Cloud Desktop (recommended)",
            "   a. Open Creative Cloud Desktop → Plugins → Manage Plugins",
            "   b. Click the gear icon → 'Install from file...'",
            f"   c. Select the downloaded .ccx file",
            "   d. Restart Photoshop",
            "",
            "## 3. Or install manually",
            f"   Copy the .ccx to: {uxp_dir}",
            f"   PowerShell: copy dcc-mcp-photoshop-bridge-{ver}.ccx \"$env:APPDATA\\Adobe\\UXP\\Plugins\\External\\\"",
        ])
    elif system == "Darwin":
        lines.extend([
            "   a. Visit: https://github.com/dcc-mcp/dcc-mcp-photoshop/releases",
            f"   b. Download: dcc-mcp-photoshop-bridge-{ver}.ccx",
            "",
            "## 2. Install via Creative Cloud Desktop (recommended)",
            "   a. Open Creative Cloud Desktop → Plugins → Manage Plugins",
            "   b. Click the gear icon → 'Install from file...'",
            f"   c. Select the downloaded .ccx file",
            "   d. Restart Photoshop",
            "",
            "## 3. Or install manually",
            f"   cp dcc-mcp-photoshop-bridge-{ver}.ccx ~/Library/Application\\ Support/Adobe/UXP/Plugins/External/",
        ])
    else:
        lines.extend([
            f"   Visit: https://github.com/dcc-mcp/dcc-mcp-photoshop/releases",
            f"   Download: dcc-mcp-photoshop-bridge-{ver}.ccx",
        ])

    lines.extend([
        "",
        "## 4. Verify installation",
        "   a. Restart Photoshop",
        "   b. The plugin starts a WebSocket server on port 9001 automatically",
        "   c. Run check_environment or verify_connection to confirm",
    ])

    return "\n".join(lines)


@skill_entry
def setup_uxp_plugin(
    version: str = "",
    method: str = "auto",
    ccx_path: str = "",
    **kwargs,
) -> dict:
    """Install the UXP .ccx plugin into Photoshop.

    Args:
        version: Plugin version to install (e.g. "0.2.0"); empty means latest.
        method: "auto" to attempt automatic install, "guide" for instructions only.
        ccx_path: Local path to a pre-downloaded .ccx file.

    Returns:
        dict: Installation result with success status and guidance.
    """
    system = platform.system()
    uxp_dir = _get_uxp_plugin_dir()

    if method == "guide":
        guide_text = _generate_guide(version)
        return {
            "success": True,
            "summary": f"Installation guide generated (UXP plugin dir: {uxp_dir})",
            "details": {
                "platform": system,
                "uxp_plugin_dir": uxp_dir,
                "guide": guide_text,
            },
            "prompt": (
                "Follow the steps above, then run verify_connection to confirm."
            ),
        }

    # auto method
    installed = False
    install_path = ""

    if ccx_path and os.path.isfile(ccx_path):
        # Use provided .ccx file
        if uxp_dir and os.path.isdir(uxp_dir):
            dest = os.path.join(uxp_dir, os.path.basename(ccx_path))
            shutil.copy2(ccx_path, dest)
            installed = True
            install_path = dest
        else:
            return {
                "success": False,
                "summary": "UXP plugins directory not found",
                "details": {
                    "platform": system,
                    "uxp_plugin_dir": uxp_dir,
                    "error": f"Directory does not exist: {uxp_dir}",
                },
                "prompt": (
                    "Use method='guide' for manual installation instructions, "
                    "or create the UXP plugins directory manually."
                ),
            }

    elif uxp_dir and os.path.isdir(uxp_dir):
        # Try to find existing .ccx in source tree
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        ccx_files = _find_ccx_files(repo_root)
        if ccx_files:
            src = ccx_files[0]
            dest = os.path.join(uxp_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            installed = True
            install_path = dest
        else:
            return {
                "success": False,
                "summary": "No .ccx file found locally",
                "details": {
                    "platform": system,
                    "uxp_plugin_dir": uxp_dir,
                    "error": "No .ccx file found in workspace. Download from GitHub Releases.",
                    "guide": _generate_guide(version),
                },
                "prompt": (
                    "Use method='guide' for step-by-step instructions, "
                    "or provide a ccx_path to a downloaded .ccx file."
                ),
            }
    else:
        return {
            "success": False,
            "summary": "UXP plugins directory not found",
            "details": {
                "platform": system,
                "uxp_plugin_dir": uxp_dir,
                "error": f"Directory does not exist: {uxp_dir}",
                "guide": _generate_guide(version),
            },
            "prompt": (
                "Install manually using the guide steps above, "
                "or create the directory and try again."
            ),
        }

    return {
        "success": installed,
        "summary": f"UXP plugin {'installed' if installed else 'failed'}",
        "details": {
            "platform": system,
            "uxp_plugin_dir": uxp_dir,
            "install_path": install_path,
        },
        "prompt": (
            "Restart Photoshop, then run start_server to launch the MCP server "
            "and verify_connection to confirm the bridge is working."
        ),
    }


def main(**kwargs) -> dict:
    return setup_uxp_plugin(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
