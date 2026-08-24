"""Photoshop host discovery facts for Install SOP preflight."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

from dcc_mcp_photoshop.install_contract import version_tuple

ExternalRunner = Callable[..., subprocess.CompletedProcess]
_ADOBE_TEAM_IDENTIFIER = "JQ525L2MZD"
_PHOTOSHOP_BUNDLE_IDENTIFIER = "com.adobe.Photoshop"
_MAX_METADATA_BYTES = 65_536


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & reparse_flag)


def path_uses_link(path: Path) -> bool:
    """Reject a selected product whose existing path is redirected by a link/reparse point."""
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if _is_link_or_reparse(current):
            return True
    return False


def _bounded_json(result: subprocess.CompletedProcess) -> dict[str, Any] | None:
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    if result.returncode != 0:
        return None
    if len(stdout.encode("utf-8", errors="replace")) > _MAX_METADATA_BYTES:
        return None
    if len(stderr.encode("utf-8", errors="replace")) > _MAX_METADATA_BYTES:
        return None
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_adobe_signer_subject(subject: str) -> bool:
    components = {component.strip().casefold() for component in subject.split(",")}
    adobe_names = {"adobe inc.", "adobe systems incorporated"}
    return any(f"cn={name}" in components for name in adobe_names) and any(
        f"o={name}" in components for name in adobe_names
    )


def _windows_host_identity(path: Path, runner: ExternalRunner) -> dict[str, Any] | None:
    if path.name.casefold() != "photoshop.exe":
        return None
    script = (
        "$ErrorActionPreference='Stop';"
        "$p=(Resolve-Path -LiteralPath $args[0]).Path;"
        "$f=[System.Diagnostics.FileVersionInfo]::GetVersionInfo($p);"
        "$s=Get-AuthenticodeSignature -LiteralPath $p;"
        "[ordered]@{status=[string]$s.Status;subject=[string]$s.SignerCertificate.Subject;"
        "company=[string]$f.CompanyName;product=[string]$f.ProductName;"
        "product_version=[string]$f.ProductVersion}|ConvertTo-Json -Compress"
    )
    powershell = "powershell.exe"
    if platform.system() == "Windows":
        system_root = os.environ.get("SystemRoot")
        if not system_root:
            return None
        trusted_powershell = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not trusted_powershell.is_file() or path_uses_link(trusted_powershell):
            return None
        powershell = str(trusted_powershell)
    try:
        result = runner(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    metadata = _bounded_json(result)
    if metadata is None:
        return None
    status = metadata.get("status")
    subject = metadata.get("subject")
    company = metadata.get("company")
    product = metadata.get("product")
    product_version = metadata.get("product_version")
    if (
        status != "Valid"
        or not isinstance(subject, str)
        or not _is_adobe_signer_subject(subject)
        or not isinstance(company, str)
        or company.strip().casefold() not in {"adobe", "adobe inc.", "adobe systems incorporated"}
        or not isinstance(product, str)
        or re.fullmatch(r"Adobe Photoshop(?: 20[0-9]{2})?", product.strip(), re.IGNORECASE) is None
        or not isinstance(product_version, str)
        or not version_tuple(product_version.strip())
    ):
        return None
    return {
        "executable": str(path),
        "version": product_version.strip(),
        "product": product.strip(),
        "publisher": "Adobe Inc.",
        "signature": "authenticode_valid",
    }


def _macos_bundle(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name.endswith(".app"):
            return parent
    return None


def _macos_host_identity(path: Path, runner: ExternalRunner) -> dict[str, Any] | None:
    bundle = _macos_bundle(path)
    if bundle is None:
        return None
    info_path = bundle / "Contents" / "Info.plist"
    try:
        if info_path.stat().st_size <= 0 or info_path.stat().st_size > 1_048_576:
            return None
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    if not isinstance(info, dict):
        return None
    version = info.get("CFBundleShortVersionString")
    product = info.get("CFBundleName")
    if (
        info.get("CFBundleIdentifier") != _PHOTOSHOP_BUNDLE_IDENTIFIER
        or info.get("CFBundleExecutable") != path.name
        or not isinstance(product, str)
        or re.fullmatch(r"Adobe Photoshop(?: 20[0-9]{2})?", product, re.IGNORECASE) is None
        or not isinstance(version, str)
        or not version_tuple(version)
        or path.parent != bundle / "Contents" / "MacOS"
    ):
        return None
    try:
        verified = runner(
            ["/usr/bin/codesign", "--verify", "--strict", "--verbose=2", str(bundle)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        displayed = runner(
            ["/usr/bin/codesign", "--display", "--verbose=4", str(bundle)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if verified.returncode != 0 or displayed.returncode != 0:
        return None
    display_text = "\n".join(value for value in (displayed.stdout, displayed.stderr) if isinstance(value, str))
    if len(display_text.encode("utf-8", errors="replace")) > _MAX_METADATA_BYTES:
        return None
    identifiers = dict(
        match.groups()
        for match in re.finditer(r"^(Identifier|TeamIdentifier)=([^\r\n]{1,256})$", display_text, re.MULTILINE)
    )
    authorities = re.findall(r"^Authority=([^\r\n]{1,256})$", display_text, re.MULTILINE)
    if (
        identifiers.get("Identifier") != _PHOTOSHOP_BUNDLE_IDENTIFIER
        or identifiers.get("TeamIdentifier") != _ADOBE_TEAM_IDENTIFIER
        or not any("Adobe Inc." in authority for authority in authorities)
    ):
        return None
    return {
        "executable": str(path),
        "version": version,
        "product": product,
        "publisher": "Adobe Inc.",
        "signature": "codesign_valid",
        "bundle_identifier": _PHOTOSHOP_BUNDLE_IDENTIFIER,
        "team_identifier": _ADOBE_TEAM_IDENTIFIER,
    }


def attest_photoshop_executable(
    path: Path,
    *,
    platform_name: str | None = None,
    runner: ExternalRunner = subprocess.run,
) -> dict[str, Any] | None:
    """Return product-derived Photoshop identity only for an Adobe-authenticated executable."""
    candidate = path.expanduser()
    try:
        if path_uses_link(candidate):
            return None
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            return None
        initial = resolved.stat()
    except OSError:
        return None
    system = platform_name or platform.system()
    if system == "Windows":
        identity = _windows_host_identity(resolved, runner)
    elif system == "Darwin":
        identity = _macos_host_identity(resolved, runner)
    else:
        identity = None
    if identity is None:
        return None
    try:
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        final = resolved.stat()
    except OSError:
        return None
    if (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns) != (
        final.st_dev,
        final.st_ino,
        final.st_size,
        final.st_mtime_ns,
    ):
        return None
    identity["bytes"] = final.st_size
    identity["sha256"] = digest.hexdigest()
    return identity


def host_version(path: Path) -> str | None:
    pattern = re.compile(r"(?:Adobe )?Photoshop (20\d{2}|\d{2}(?:\.\d+)?)", re.IGNORECASE)
    for component in reversed(path.parts):
        match = pattern.fullmatch(component)
        if match:
            return match.group(1)
    return None


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
