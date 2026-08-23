"""Photoshop host discovery facts for Install SOP preflight."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path
from typing import Iterable


def host_version(path: Path) -> str | None:
    match = re.search(r"Photoshop\s+(20\d{2}|\d{2}(?:\.\d+)?)", str(path), re.IGNORECASE)
    return match.group(1) if match else None


def _default_roots(platform_name: str) -> list[Path]:
    if platform_name == "Windows":
        roots = []
        for name in ("ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(name)
            if value:
                roots.append(Path(value) / "Adobe")
        return roots
    if platform_name == "Darwin":
        return [Path("/Applications")]
    return []


def discover_photoshop_executable(
    platform_name: str | None = None,
    roots: Iterable[Path] | None = None,
) -> tuple[Path | None, str | None]:
    """Return the newest executable from Adobe's Windows/macOS layouts."""
    system = platform_name or platform.system()
    search_roots = list(_default_roots(system) if roots is None else roots)
    candidates: list[tuple[int, Path, str]] = []
    if system == "Windows":
        for root in search_roots:
            for product in root.glob("Adobe Photoshop 20*"):
                executable = product / "Photoshop.exe"
                version = host_version(product)
                if executable.is_file() and version:
                    candidates.append((int(version), executable, version))
    elif system == "Darwin":
        for root in search_roots:
            for product in root.glob("Adobe Photoshop 20*"):
                version = host_version(product)
                if not version:
                    continue
                executable = (
                    product / f"Adobe Photoshop {version}.app" / "Contents" / "MacOS" / f"Adobe Photoshop {version}"
                )
                if executable.is_file():
                    candidates.append((int(version), executable, version))
    if not candidates:
        return None, None
    _, executable, version = max(candidates, key=lambda item: item[0])
    return executable, version
