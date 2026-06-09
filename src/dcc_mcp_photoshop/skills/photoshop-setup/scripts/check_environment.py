"""Check the system environment for dcc-mcp-photoshop prerequisites."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys

from dcc_mcp_core.skill import skill_entry


def _get_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _check_pip() -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _get_installed_packages() -> dict[str, str]:
    """Return dict of relevant installed packages and their versions."""
    packages = {}
    try:
        import importlib.metadata
        for name in ("dcc-mcp-photoshop", "dcc-mcp-core", "websockets"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
    except Exception:
        pass
    return packages


def _check_port(host: str, port: int) -> bool:
    """Check if a port is listening."""
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _check_photoshop_process() -> bool:
    """Check if Photoshop is running (platform-specific)."""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Photoshop.exe"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "Photoshop.exe" in result.stdout
        elif system == "Darwin":
            result = subprocess.run(
                ["pgrep", "-x", "Adobe Photoshop"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        else:
            result = subprocess.run(
                ["pgrep", "-x", "photoshop"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@skill_entry
def check_environment(verbose: bool = False, **kwargs) -> dict:
    """Check system prerequisites for dcc-mcp-photoshop.

    Args:
        verbose: Show detailed system information.

    Returns:
        dict: Environment status with all prerequisites.
    """
    python_version = _get_python_version()
    pip_available = _check_pip()
    packages = _get_installed_packages()
    photoshop_running = _check_photoshop_process()
    uxp_port_open = _check_port("127.0.0.1", 9001)

    # Parse Python version check
    major, minor, *_ = (int(v) for v in python_version.split("."))
    python_ok = major >= 3 and minor >= 8

    summary_parts = []
    if python_ok:
        summary_parts.append(f"Python {python_version}")
    else:
        summary_parts.append(f"Python {python_version} (need >=3.8)")

    for name, ver in packages.items():
        if ver:
            summary_parts.append(f"{name}=={ver}")
        else:
            summary_parts.append(f"{name} (not installed)")

    if photoshop_running:
        summary_parts.append("Photoshop running")
    else:
        summary_parts.append("Photoshop not detected")

    if uxp_port_open:
        summary_parts.append("UXP port 9001 open")

    result = {
        "python": {
            "version": python_version,
            "executable": sys.executable,
            "ok": python_ok,
        },
        "pip": {"available": pip_available},
        "packages": packages,
        "photoshop": {
            "running": photoshop_running,
            "platform": platform.system(),
        },
        "uxp_plugin": {
            "port_open": uxp_port_open,
            "port": 9001,
        },
        "system": {
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }

    if verbose and packages.get("dcc-mcp-photoshop"):
        try:
            from dcc_mcp_photoshop import __version__
            result["dcc_mcp_photoshop_version"] = __version__
        except Exception:
            pass

    return {
        "summary": " | ".join(summary_parts),
        "all_ok": all([
            python_ok,
            pip_available or packages.get("dcc-mcp-photoshop"),
        ]),
        "details": result,
        "prompt": (
            "Use install_package to install dcc-mcp-photoshop, "
            "or setup_uxp_plugin to install the UXP plugin."
        ),
    }


def main(**kwargs) -> dict:
    return check_environment(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
