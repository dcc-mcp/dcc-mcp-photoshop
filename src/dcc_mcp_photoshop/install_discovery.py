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

from dcc_mcp_photoshop.install_contract import HOST_ROOTS_ENV, version_tuple

ExternalRunner = Callable[..., subprocess.CompletedProcess]
_ADOBE_TEAM_IDENTIFIER = "JQ525L2MZD"
_PHOTOSHOP_BUNDLE_IDENTIFIER = "com.adobe.Photoshop"
_MAX_METADATA_BYTES = 65_536
_SIGNATURE_VALID = "authenticode_valid"
_SIGNATURE_HASH_MISMATCH = "authenticode_hash_mismatch"
_AUTHENTICODE_VALID = "Valid"
_AUTHENTICODE_HASH_MISMATCH = "HashMismatch"
_ADOBE_PRODUCT_GLOB = "Adobe Photoshop*"
_WINDOWS_HOST_EXECUTABLE = "Photoshop.exe"
_PORTABLE_BIN_DIR = "bin"
# Bounded portable layouts: <root>/<version>/bin/Photoshop.exe and <root>/<bundle>/<version>/bin.
_PORTABLE_WINDOWS_GLOBS = (
    f"*/{_PORTABLE_BIN_DIR}/{_WINDOWS_HOST_EXECUTABLE}",
    f"*/*/{_PORTABLE_BIN_DIR}/{_WINDOWS_HOST_EXECUTABLE}",
)
_BARE_VERSION = re.compile(r"20[0-9]{2}|[1-9][0-9](?:\.[0-9]+)?")


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


def _powershell_single_quoted(value: str) -> str:
    """Quote a value for a PowerShell single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def _windows_host_identity(
    path: Path,
    runner: ExternalRunner,
    *,
    allow_unverified: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return the Windows host identity, or ``None`` and the check that rejected it."""
    if path.name.casefold() != _WINDOWS_HOST_EXECUTABLE.casefold():
        return None, f"the executable is not named {_WINDOWS_HOST_EXECUTABLE}"
    script = (
        "$ErrorActionPreference='Stop';"
        f"$p=(Resolve-Path -LiteralPath {_powershell_single_quoted(str(path))}).Path;"
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
            return None, "SystemRoot is not configured"
        trusted_powershell = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not trusted_powershell.is_file() or path_uses_link(trusted_powershell):
            return None, "no trusted Windows PowerShell host was found"
        powershell = str(trusted_powershell)
    try:
        # The host path is inlined into the command text: `powershell -Command <script> <arg>`
        # does not populate `$args`, so a trailing argument would be executed as its own
        # statement and `$args[0]` would be null.
        result = runner(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "the Authenticode probe could not be executed"
    metadata = _bounded_json(result)
    if metadata is None:
        return None, "the Authenticode probe returned unusable metadata"
    status = metadata.get("status")
    subject = metadata.get("subject")
    company = metadata.get("company")
    product = metadata.get("product")
    product_version = metadata.get("product_version")
    if not isinstance(subject, str) or not _is_adobe_signer_subject(subject):
        return None, "the signer subject is not Adobe"
    if not isinstance(company, str) or company.strip().casefold() not in {
        "adobe",
        "adobe inc.",
        "adobe systems incorporated",
    }:
        return None, "the product company is not Adobe"
    if (
        not isinstance(product, str)
        or re.fullmatch(r"Adobe Photoshop(?: 20[0-9]{2})?", product.strip(), re.IGNORECASE) is None
    ):
        return None, "the product name is not Adobe Photoshop"
    if not isinstance(product_version, str) or not version_tuple(product_version.strip()):
        return None, "the product version is not a usable release version"
    signature = _windows_signature_label(status, allow_unverified=allow_unverified)
    if signature is None:
        return None, _windows_signature_rejection(status, allow_unverified=allow_unverified)
    return {
        "executable": str(path),
        "version": product_version.strip(),
        "product": product.strip(),
        "publisher": "Adobe Inc.",
        "signature": signature,
        "signature_status": str(status),
    }, None


def _windows_signature_label(status: Any, *, allow_unverified: bool) -> str | None:
    """Map an Authenticode status onto an accepted provenance label.

    A ``HashMismatch`` host reports an Adobe signer subject and Adobe product metadata, but its
    bytes no longer match the signed digest. Repackaged hosts land here, and so does a forged
    signature blob that merely embeds Adobe's public certificate, because the version resource is
    attacker-controlled. The mismatch therefore stays fatal unless an operator accepts it.
    """
    if status == _AUTHENTICODE_VALID:
        return _SIGNATURE_VALID
    if status == _AUTHENTICODE_HASH_MISMATCH and allow_unverified:
        return _SIGNATURE_HASH_MISMATCH
    return None


def _windows_signature_rejection(status: Any, *, allow_unverified: bool) -> str:
    reported = status if isinstance(status, str) and status else "unknown"
    if status == _AUTHENTICODE_HASH_MISMATCH:
        return (
            f"Authenticode status is {reported}; the host bytes were changed after signing "
            "(re-run with --allow-unverified-host to accept a repackaged host you own)"
        )
    if allow_unverified:
        return f"Authenticode status is {reported}; only {_AUTHENTICODE_HASH_MISMATCH} can be accepted"
    return f"Authenticode status is {reported}, not {_AUTHENTICODE_VALID}"


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


def _host_identity_with_reason(
    path: Path,
    *,
    platform_name: str | None,
    runner: ExternalRunner,
    allow_unverified: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    candidate = path.expanduser()
    try:
        if path_uses_link(candidate):
            return None, "the executable path is redirected by a link or reparse point"
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            return None, "the executable is missing or empty"
        initial = resolved.stat()
    except OSError:
        return None, "the executable could not be inspected"
    system = platform_name or platform.system()
    if system == "Windows":
        identity, reason = _windows_host_identity(resolved, runner, allow_unverified=allow_unverified)
    elif system == "Darwin":
        identity, reason = _macos_host_identity(resolved, runner), None
    else:
        return None, f"host provenance is unsupported on {system or 'this platform'}"
    if identity is None:
        return None, reason or "the executable is not an Adobe-authenticated Photoshop host"
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
        return None, "the executable could not be read"
    if (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns) != (
        final.st_dev,
        final.st_ino,
        final.st_size,
        final.st_mtime_ns,
    ):
        return None, "the executable changed while it was being read"
    identity["bytes"] = final.st_size
    identity["sha256"] = digest.hexdigest()
    return identity, None


def attest_photoshop_executable(
    path: Path,
    *,
    platform_name: str | None = None,
    runner: ExternalRunner = subprocess.run,
    allow_unverified: bool = False,
) -> dict[str, Any] | None:
    """Return product-derived Photoshop identity only for an Adobe-authenticated executable.

    ``allow_unverified`` is an operator opt-in that accepts a Windows host whose signature hash no
    longer matches its bytes. Every other identity fact still has to hold, and an unsigned or
    untrusted host is never accepted.
    """
    identity, _reason = _host_identity_with_reason(
        path,
        platform_name=platform_name,
        runner=runner,
        allow_unverified=allow_unverified,
    )
    return identity


def host_provenance_reason(
    path: Path,
    *,
    platform_name: str | None = None,
    runner: ExternalRunner = subprocess.run,
    allow_unverified: bool = False,
) -> str | None:
    """Explain why a host was rejected, for the failure path of ``attest_photoshop_executable``."""
    identity, reason = _host_identity_with_reason(
        path,
        platform_name=platform_name,
        runner=runner,
        allow_unverified=allow_unverified,
    )
    return None if identity is not None else (reason or "the host is not Adobe-authenticated")


def host_version(path: Path) -> str | None:
    pattern = re.compile(r"(?:Adobe )?Photoshop (20\d{2}|\d{2}(?:\.\d+)?)", re.IGNORECASE)
    for component in reversed(path.parts):
        match = pattern.fullmatch(component)
        if match:
            return match.group(1)
    return None


def _configured_roots() -> list[Path]:
    """Return operator-configured search roots for package-managed or portable hosts."""
    configured = os.environ.get(HOST_ROOTS_ENV, "")
    roots: list[Path] = []
    for entry in configured.split(os.pathsep):
        entry = entry.strip()
        if entry:
            roots.append(Path(entry).expanduser())
    return roots


def _default_roots(platform_name: str) -> list[Path]:
    roots: list[Path] = []
    if platform_name == "Windows":
        for name in ("ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(name)
            if value:
                roots.append(Path(value) / "Adobe")
    elif platform_name == "Darwin":
        roots.append(Path("/Applications"))
    return roots + _configured_roots()


def _directory_version_token(name: str) -> str | None:
    """Return the version token carried by a product or portable layout directory name."""
    token = name.strip()
    if not token:
        return None
    known = host_version(Path(token))
    if known:
        return known
    match = _BARE_VERSION.fullmatch(token)
    return match.group(0) if match else None


def _candidate_rank(token: str | None) -> int:
    try:
        return int(float(token)) if token else 0
    except ValueError:
        return 0


def _windows_candidates(root: Path) -> list[tuple[int, Path, str | None]]:
    found: list[tuple[int, Path, str | None]] = []
    seen: set[Path] = set()

    def add(executable: Path, token: str | None) -> None:
        if not executable.is_file() or executable in seen:
            return
        seen.add(executable)
        found.append((_candidate_rank(token), executable, token))

    # Classic Adobe layout, plus a portable payload staged inside a versioned product directory.
    for product in root.glob(_ADOBE_PRODUCT_GLOB):
        if not product.is_dir():
            continue
        token = _directory_version_token(product.name)
        for executable in (product / _WINDOWS_HOST_EXECUTABLE, product / _PORTABLE_BIN_DIR / _WINDOWS_HOST_EXECUTABLE):
            if token:
                add(executable, token)
    # Package-manager layout: <root>/<version>/bin/Photoshop.exe, optionally under a bundle directory.
    for pattern in _PORTABLE_WINDOWS_GLOBS:
        for executable in root.glob(pattern):
            add(executable, _directory_version_token(executable.parent.parent.name))
    return found


def discover_photoshop_executable(
    platform_name: str | None = None,
    roots: Iterable[Path] | None = None,
) -> tuple[Path | None, str | None]:
    """Return the newest executable from Adobe's Windows/macOS and portable layouts."""
    system = platform_name or platform.system()
    search_roots = list(_default_roots(system) if roots is None else roots)
    candidates: list[tuple[int, Path, str | None]] = []
    if system == "Windows":
        for root in search_roots:
            candidates.extend(_windows_candidates(root))
    elif system == "Darwin":
        for root in search_roots:
            for product in root.glob(_ADOBE_PRODUCT_GLOB):
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
    # Rank by version, then by path so equally ranked layouts stay deterministic.
    _, executable, version = max(candidates, key=lambda item: (item[0], str(item[1])))
    return executable, version
