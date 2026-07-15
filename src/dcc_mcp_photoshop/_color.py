"""Color conversion helpers shared by Photoshop skill scripts."""

from __future__ import annotations


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a three- or six-digit hex color to integer RGB channels."""
    normalized = value.strip().lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(character * 2 for character in normalized)
    if len(normalized) != 6:
        raise ValueError(f"Expected a 3- or 6-digit hex color, got {value!r}")
    try:
        return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"Invalid hex color: {value!r}") from exc


def solid_color_payload(value: str) -> dict:
    """Return the serializable color payload expected by adobepy's UXP bridge."""
    red, green, blue = hex_to_rgb(value)
    return {"rgb": {"red": red, "green": green, "blue": blue}}
