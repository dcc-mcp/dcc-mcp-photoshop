"""Stage the adobepy UXP bridge for Adobe Photoshop."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from dcc_mcp_core.skill import skill_entry


def _default_bridge_dir() -> Path:
    if platform.system() == "Windows":
        root = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    else:
        root = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(root) / "adobepy" / "bridges" / "photoshop"


def _guide(bridge_dir: Path) -> str:
    manifest = bridge_dir / "manifest.json"
    return "\n".join(
        [
            "1. Install the adobepy release bundle so the adobepy CLI is on PATH.",
            f'2. Run: adobepy install-bridge photoshop --dest "{bridge_dir}"',
            "3. In Photoshop, enable Plugins > Enable Developer Mode.",
            "4. Open Adobe UXP Developer Tool and add the generated manifest:",
            f"   {manifest}",
            "5. Select the plugin and click Load, then verify the broker reports a Photoshop session.",
        ]
    )


@skill_entry
def setup_uxp_plugin(
    method: str = "auto",
    bridge_dir: str = "",
    adobepy_executable: str = "",
    **kwargs,
) -> dict:
    """Stage the adobepy Photoshop bridge without claiming Adobe loaded it.

    Adobe owns developer-plugin registration and loading. This tool generates
    the bridge files; UXP Developer Tool performs the explicit host load.
    """
    destination = Path(bridge_dir).expanduser() if bridge_dir else _default_bridge_dir()
    guide = _guide(destination)

    if method == "guide":
        return {
            "success": True,
            "summary": "adobepy bridge setup guide generated",
            "details": {"state": "guide", "bridge_dir": str(destination), "guide": guide},
            "prompt": guide,
        }

    executable = adobepy_executable or shutil.which("adobepy")
    if not executable:
        return {
            "success": False,
            "summary": "adobepy CLI not found; Photoshop bridge was not staged",
            "details": {"state": "not_staged", "bridge_dir": str(destination), "guide": guide},
            "prompt": guide,
        }

    try:
        result = subprocess.run(
            [executable, "install-bridge", "photoshop", "--dest", str(destination)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "success": False,
            "summary": "adobepy bridge staging failed",
            "details": {"state": "not_staged", "bridge_dir": str(destination), "error": str(exc)},
            "prompt": guide,
        }

    if result.returncode != 0:
        return {
            "success": False,
            "summary": "adobepy bridge staging failed",
            "details": {
                "state": "not_staged",
                "bridge_dir": str(destination),
                "error": result.stderr.strip() or result.stdout.strip(),
            },
            "prompt": guide,
        }

    return {
        "success": True,
        "summary": "adobepy Photoshop bridge staged; Adobe host load is still required",
        "details": {"state": "staged", "bridge_dir": str(destination), "manifest": str(destination / "manifest.json")},
        "prompt": guide,
    }


def main(**kwargs) -> dict:
    return setup_uxp_plugin(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
