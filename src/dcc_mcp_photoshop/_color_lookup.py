"""Pure-Python ``.cube`` 3D LUT parsing and color-lookup math.

This module is host-agnostic and dependency-free: it reads the standard
``.cube`` 3D LUT format and applies a color-lookup transform to normalized
``[0, 1]`` RGB triples using trilinear interpolation (RED-fastest ordering).
It is used by the ``apply_color_lookup`` skill to validate a LUT before any
host call, and by the offline regression suite to pin down the *expected*
pixel behavior of a LUT.

OFFLINE ONLY. This module does not talk to Photoshop, MCP, or adobepy. It is
NOT native acceptance evidence: it cannot prove that a real Photoshop document
loaded the LUT, toggled it, or exported a copy. Those checks remain a separate
native end-to-end gate that requires a deployed, authenticated broker.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

IDENTITY_TOLERANCE = 1e-6
TRANSFORM_THRESHOLD = 0.05
COLOR_SPACE = "sRGB-ish unit cube [0,1]; trilinear interpolation; LUT applied in gamma space (assumption, recorded)"

# Module-level aliases are evaluated at import time, so use typing.Tuple for
# Python 3.8 compatibility (builtin ``tuple[...]`` is not subscriptable there).
_RGBTriple = Tuple[float, float, float]


@dataclass(frozen=True)
class CubeLut:
    """Parsed 3D LUT with RED-fastest lattice ordering."""

    size: int
    data: tuple[_RGBTriple, ...]
    title: str = "synthetic"
    domain_min: _RGBTriple = (0.0, 0.0, 0.0)
    domain_max: _RGBTriple = (1.0, 1.0, 1.0)


def parse_cube(text: str) -> CubeLut:
    """Parse a standard ``.cube`` 3D LUT string.

    Recognizes ``TITLE``, ``DOMAIN_MIN``, ``DOMAIN_MAX`` and ``LUT_3D_SIZE``
    directives plus the ``N^3`` data lines (each three floats). Raises
    ``ValueError`` for malformed, non-3D, non-finite, or under/over-populated
    LUTs so a broken file can never reach the host.
    """
    size: int | None = None
    title = "synthetic"
    domain_min: _RGBTriple = (0.0, 0.0, 0.0)
    domain_max: _RGBTriple = (1.0, 1.0, 1.0)
    data: list[_RGBTriple] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        if keyword == "TITLE":
            quoted = line.split('"')
            title = quoted[1] if len(quoted) >= 2 else " ".join(parts[1:])
            continue
        if keyword == "DOMAIN_MIN":
            domain_min = _parse_triple(parts, "DOMAIN_MIN")
            continue
        if keyword == "DOMAIN_MAX":
            domain_max = _parse_triple(parts, "DOMAIN_MAX")
            continue
        if keyword == "LUT_3D_SIZE":
            if len(parts) != 2:
                raise ValueError("LUT_3D_SIZE expects a single integer")
            size = int(parts[1])
            # Validate the declared size immediately so the capacity guard
            # below is always bounded to a real lattice.
            if size < 2 or size > 256:
                raise ValueError("LUT_3D_SIZE out of range [2, 256]")
            continue
        if keyword.startswith("LUT_"):
            raise ValueError(f"unsupported LUT directive: {keyword}")
        if len(parts) != 3:
            raise ValueError(f"malformed .cube data line: {line!r}")
        # Stop as soon as the declared lattice is full; do not buffer an
        # unbounded number of extra data lines before the final count check.
        if size is not None and len(data) >= size**3:
            raise ValueError(f"more than {size**3} data lines")
        data.append(_parse_triple(parts, "data line"))

    if size is None:
        raise ValueError("missing LUT_3D_SIZE")
    if len(data) != size**3:
        raise ValueError(f"expected {size**3} data lines, got {len(data)}")
    for triple in data:
        if any(not math.isfinite(value) for value in triple):
            raise ValueError("LUT data contains a non-finite value")
    # A non-finite domain bound (nan/inf) passes float() and the ``hi <= lo``
    # comparison below is False for nan, so validate finiteness explicitly
    # before the range check. Otherwise sample() would silently pin a channel.
    if any(not math.isfinite(value) for value in (*domain_min, *domain_max)):
        raise ValueError("LUT domain contains a non-finite value")
    if any(hi <= lo for lo, hi in zip(domain_min, domain_max)):
        raise ValueError("invalid LUT domain")

    return CubeLut(
        size=size,
        data=tuple(data),
        title=title,
        domain_min=domain_min,
        domain_max=domain_max,
    )


def _parse_triple(parts: list[str], label: str) -> _RGBTriple:
    # A directive line carries its keyword at index 0; a data line carries the
    # three numbers at indices 0..2. Normalize both cases. A domain directive
    # must have exactly three numeric fields after its keyword: reject extra
    # fields instead of silently truncating them.
    if parts[0].upper() in {"DOMAIN_MIN", "DOMAIN_MAX"}:
        number_tokens = parts[1:]
    else:
        number_tokens = parts[0:3]
    if len(number_tokens) != 3:
        raise ValueError(f"{label} expects three numeric values")
    try:
        parsed = tuple(float(token) for token in number_tokens)
    except ValueError as exc:
        raise ValueError(f"{label} expects three numeric values") from exc
    return (parsed[0], parsed[1], parsed[2])


def _format_cube_float(value: float) -> str:
    # A fixed 9-decimal format rounds any magnitude below 5e-10 to
    # "0.000000000", which silently collapses a valid non-zero-width domain
    # into a zero-width one on a write/parse round-trip. repr() of a float is
    # its shortest round-trippable representation: ordinary values stay clean
    # decimals, and tiny bounds keep scientific notation (e.g. 1e-10), which
    # float() parses back exactly.
    return repr(float(value))


def write_cube(lut: CubeLut) -> str:
    """Serialize a :class:`CubeLut` back to standard ``.cube`` text."""
    lines = [
        f'TITLE "{lut.title}"',
        "DOMAIN_MIN " + " ".join(_format_cube_float(value) for value in lut.domain_min),
        "DOMAIN_MAX " + " ".join(_format_cube_float(value) for value in lut.domain_max),
        f"LUT_3D_SIZE {lut.size}",
    ]
    lines.extend(" ".join(_format_cube_float(value) for value in triple) for triple in lut.data)
    return "\n".join(lines) + "\n"


def identity_lut(size: int = 2, *, title: str = "identity") -> CubeLut:
    """Build a synthetic identity LUT: every lattice point maps to itself."""
    if size < 2:
        raise ValueError("size must be >= 2")
    span = size - 1
    data = tuple((r / span, g / span, b / span) for b in range(size) for g in range(size) for r in range(size))
    return CubeLut(size=size, data=data, title=title)


def warm_lut(size: int = 2, *, title: str = "warm") -> CubeLut:
    """Build a synthetic, non-identity warm LUT for regression testing.

    Output at each lattice point follows a recorded warm transform of the
    normalized input coordinates. This is deliberately NOT an identity so the
    suite can prove a color-lookup actually changes pixels.
    """
    if size < 2:
        raise ValueError("size must be >= 2")
    span = size - 1
    data = []
    for b in range(size):
        for g in range(size):
            for r in range(size):
                rr, gg, bb = r / span, g / span, b / span
                data.append(
                    (
                        min(1.0, 0.15 + 0.80 * gg),
                        min(1.0, 0.10 + 0.85 * bb),
                        min(1.0, 0.05 + 0.90 * rr),
                    )
                )
    return CubeLut(size=size, data=tuple(data), title=title)


def is_identity(lut: CubeLut, *, tolerance: float = IDENTITY_TOLERANCE) -> bool:
    """Return ``True`` when every lattice point equals its input within tolerance.

    "Input" is the domain coordinate that maps to each lattice point, derived
    from ``domain_min`` / ``domain_max``. For the default unit domain this is
    ``grid / span``; for a non-default domain the skill must not report a LUT
    as an identity transform when its sampled outputs do not match those
    domain coordinates.
    """
    span = lut.size - 1
    for b in range(lut.size):
        for g in range(lut.size):
            for r in range(lut.size):
                index = r + lut.size * g + lut.size * lut.size * b
                grid = (r, g, b)
                expected = tuple(
                    lut.domain_min[channel]
                    + (grid[channel] / span) * (lut.domain_max[channel] - lut.domain_min[channel])
                    for channel in range(3)
                )
                if any(abs(lut.data[index][channel] - expected[channel]) > tolerance for channel in range(3)):
                    return False
    return True


def _lerp3(a: _RGBTriple, b: _RGBTriple, t: float) -> _RGBTriple:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def sample(lut: CubeLut, red: float, green: float, blue: float) -> _RGBTriple:
    """Trilinearly sample the LUT for one normalized ``[0,1]`` RGB triple."""

    def normalize(value: float, lo: float, hi: float) -> float:
        if hi == lo:
            return 0.0
        return min(1.0, max(0.0, (value - lo) / (hi - lo)))

    n = lut.size
    r = normalize(red, lut.domain_min[0], lut.domain_max[0]) * (n - 1)
    g = normalize(green, lut.domain_min[1], lut.domain_max[1]) * (n - 1)
    b = normalize(blue, lut.domain_min[2], lut.domain_max[2]) * (n - 1)
    r0, g0, b0 = int(r), int(g), int(b)
    r1, g1, b1 = min(r0 + 1, n - 1), min(g0 + 1, n - 1), min(b0 + 1, n - 1)
    fr, fg, fb = r - r0, g - g0, b - b0

    def at(ri: int, gi: int, bi: int) -> _RGBTriple:
        return lut.data[ri + n * gi + n * n * bi]

    c00 = _lerp3(at(r0, g0, b0), at(r1, g0, b0), fr)
    c10 = _lerp3(at(r0, g1, b0), at(r1, g1, b0), fr)
    c01 = _lerp3(at(r0, g0, b1), at(r1, g0, b1), fr)
    c11 = _lerp3(at(r0, g1, b1), at(r1, g1, b1), fr)
    return _lerp3(_lerp3(c00, c10, fg), _lerp3(c01, c11, fg), fb)


def apply_lut(
    pixels: list[_RGBTriple],
    lut: CubeLut,
    *,
    enabled: bool = True,
) -> list[_RGBTriple]:
    """Apply a LUT to pixels, returning a NEW list (source is never mutated).

    ``enabled=False`` is the toggle-off path: it returns a copy of the source
    pixels unchanged. This models the expected native behavior for the offline
    regression suite only; it does not operate on a Photoshop document.
    """
    if not enabled:
        return list(pixels)
    return [sample(lut, pixel[0], pixel[1], pixel[2]) for pixel in pixels]


def max_abs_diff(a: list[_RGBTriple], b: list[_RGBTriple]) -> float:
    """Maximum per-channel absolute difference between two pixel lists."""
    if len(a) != len(b):
        raise ValueError("pixel lists must have equal length")
    if not a:
        return 0.0
    return max(abs(left[channel] - right[channel]) for left, right in zip(a, b) for channel in range(3))
