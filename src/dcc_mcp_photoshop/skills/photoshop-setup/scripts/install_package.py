"""Install or upgrade dcc-mcp-photoshop and its dependencies via pip."""

from __future__ import annotations

import subprocess
import sys

from dcc_mcp_core.skill import skill_entry


def _pip_install(args: list[str]) -> dict:
    """Run pip install with the given arguments and return result."""
    cmd = [sys.executable, "-m", "pip", "install"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        success = result.returncode == 0
        return {
            "success": success,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "pip install timed out after 120 seconds",
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "pip not found",
            "command": " ".join(cmd),
        }


@skill_entry
def install_package(
    version: str = "",
    upgrade: bool = False,
    editable: bool = False,
    source_path: str = "",
    **kwargs,
) -> dict:
    """Install or upgrade dcc-mcp-photoshop via pip.

    Args:
        version: Specific version to install (e.g. "0.2.0"); empty means latest.
        upgrade: Upgrade to the latest version if already installed.
        editable: Install in editable/development mode from source.
        source_path: Local source path for editable install.

    Returns:
        dict: Installation result with success status and logs.
    """
    pip_args = []

    if upgrade:
        pip_args.append("--upgrade")

    if editable:
        if not source_path:
            return {
                "success": False,
                "summary": "Editable install requires source_path",
                "details": {
                    "error": "source_path is required when editable=True",
                },
                "prompt": ("Clone the repo first: git clone https://github.com/dcc-mcp/dcc-mcp-photoshop"),
            }
        pip_args.extend(["-e", source_path])
    elif version:
        pip_args.append(f"dcc-mcp-photoshop=={version}")
    else:
        pip_args.append("dcc-mcp-photoshop")

    result = _pip_install(pip_args)

    if result["success"]:
        # Verify the installed version
        try:
            from dcc_mcp_photoshop import __version__  # noqa: PLC0415

            installed = __version__
        except Exception:
            installed = "unknown"

        summary = f"dcc-mcp-photoshop installed (version: {installed})"
        prompt = "Use setup_uxp_plugin to stage and load the adobepy bridge, then start_server."
    else:
        summary = "Installation failed"
        prompt = "Check Python/pip setup with check_environment, then retry."

    return {
        "summary": summary,
        "success": result["success"],
        "details": {
            "installed_version": installed if result["success"] else None,
            "pip_stdout": result["stdout"],
            "pip_stderr": result["stderr"],
        },
        "prompt": prompt,
    }


def main(**kwargs) -> dict:
    return install_package(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
