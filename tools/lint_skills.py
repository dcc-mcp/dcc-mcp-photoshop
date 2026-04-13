#!/usr/bin/env python3
"""Lint SKILL.md files in the dcc-mcp-photoshop skills directory.

Usage::

    python tools/lint_skills.py                    # lint all skills
    python tools/lint_skills.py --error-only       # only report ERRORs
    python tools/lint_skills.py --skills-root path # custom skills root
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_SCRIPT_EXTENSIONS: Set[str] = {
    ".py",
    ".js",
    ".jsx",
}

VALID_DCC_VALUES: Set[str] = {
    "photoshop",
    "python",
}

# For this project all skills must target photoshop
PROJECT_DCC = "photoshop"

CONFLICT_MARKER_RE = re.compile(r"^(<{7}|={7}|>{7})", re.MULTILINE)
SEMVER_RE = re.compile(r"^\d+\.\d+(\.\d+)?(-[\w.]+)?(\+[\w.]+)?$")
NAME_VALID_RE = re.compile(r"^[a-z0-9-]+$")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LintIssue:
    skill: str
    file: str
    severity: str  # "ERROR" | "WARNING"
    rule: str
    message: str


@dataclass
class SkillInfo:
    name: str
    skill_dir: Path
    scripts: List[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# YAML frontmatter parsing (no external dependency)
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> Tuple[Optional[Dict], str]:
    """Extract YAML frontmatter from a markdown string.

    Returns (metadata_dict or None, body_text).
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return None, text

    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return None, text

    # Find the closing ---
    rest = stripped[3:].lstrip("\n")
    end = rest.find("\n---")
    if end == -1:
        return None, text

    yaml_text = rest[:end]
    body = rest[end + 4:]

    try:
        metadata = yaml.safe_load(yaml_text)
    except Exception:
        return None, text

    return metadata or {}, body


# ---------------------------------------------------------------------------
# Lint rules
# ---------------------------------------------------------------------------


def _lint_skill(skill_dir: Path, project_root: Path) -> List[LintIssue]:
    issues: List[LintIssue] = []
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    rel = lambda p: str(p.relative_to(project_root))  # noqa: E731

    # ── R001: SKILL.md must exist ─────────────────────────────────────────
    if not skill_md.exists():
        issues.append(LintIssue(skill_name, rel(skill_dir), "ERROR", "R001", "SKILL.md not found"))
        return issues  # no point continuing

    content = skill_md.read_text(encoding="utf-8")

    # ── R002: No conflict markers ─────────────────────────────────────────
    if CONFLICT_MARKER_RE.search(content):
        issues.append(LintIssue(skill_name, rel(skill_md), "ERROR", "R002", "Git conflict markers found"))

    # ── Parse frontmatter ─────────────────────────────────────────────────
    meta, _ = _parse_frontmatter(content)
    if meta is None:
        issues.append(LintIssue(skill_name, rel(skill_md), "ERROR", "R003", "No YAML frontmatter found"))
        return issues

    # ── R004: Required fields ─────────────────────────────────────────────
    for field_name in ("name", "description", "version"):
        if not meta.get(field_name):
            issues.append(
                LintIssue(skill_name, rel(skill_md), "ERROR", "R004", f"Missing required field: '{field_name}'")
            )

    # ── R005: name must be lowercase-with-dashes ──────────────────────────
    meta_name = meta.get("name", "")
    if meta_name and not NAME_VALID_RE.match(meta_name):
        issues.append(
            LintIssue(skill_name, rel(skill_md), "ERROR", "R005", f"'name' must match [a-z0-9-], got: {meta_name!r}")
        )

    # ── R006: version must be semver-ish ──────────────────────────────────
    version = str(meta.get("version", ""))
    if version and not SEMVER_RE.match(version):
        issues.append(
            LintIssue(skill_name, rel(skill_md), "WARNING", "R006", f"'version' should be semver, got: {version!r}")
        )

    # ── R007: dcc must be 'photoshop' ────────────────────────────────────
    dcc = meta.get("dcc", "")
    if dcc and dcc not in VALID_DCC_VALUES:
        issues.append(
            LintIssue(
                skill_name, rel(skill_md), "ERROR", "R007",
                f"'dcc' must be one of {sorted(VALID_DCC_VALUES)}, got: {dcc!r}"
            )
        )
    if dcc and dcc != PROJECT_DCC:
        issues.append(
            LintIssue(
                skill_name, rel(skill_md), "WARNING", "R008",
                f"'dcc' should be '{PROJECT_DCC}' for this project, got: {dcc!r}"
            )
        )

    # ── R009: tools list must reference existing scripts ─────────────────
    tools = meta.get("tools", [])
    if not isinstance(tools, list):
        issues.append(LintIssue(skill_name, rel(skill_md), "ERROR", "R009", "'tools' must be a list"))
    else:
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            source = tool.get("source_file", "")
            if not source:
                continue
            script_path = skill_dir / "scripts" / source
            if not script_path.exists():
                issues.append(
                    LintIssue(
                        skill_name, rel(skill_md), "ERROR", "R010",
                        f"Tool source file not found: scripts/{source}"
                    )
                )
            elif script_path.suffix not in SUPPORTED_SCRIPT_EXTENSIONS:
                issues.append(
                    LintIssue(
                        skill_name, rel(skill_md), "WARNING", "R011",
                        f"Unexpected script extension {script_path.suffix!r} for {source}"
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint SKILL.md files for dcc-mcp-photoshop")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "dcc_mcp_photoshop" / "skills",
        help="Root directory containing skill subdirectories",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Project root (used for relative paths in output)",
    )
    parser.add_argument(
        "--error-only",
        action="store_true",
        help="Only report ERROR-level issues (exit 1 if any errors found)",
    )
    args = parser.parse_args()

    if not args.skills_root.exists():
        print(f"Skills root not found: {args.skills_root}")
        print("No skills to lint — OK")
        return 0

    skill_dirs = [d for d in sorted(args.skills_root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if not skill_dirs:
        print("No skill directories found — OK")
        return 0

    all_issues: List[LintIssue] = []
    for skill_dir in skill_dirs:
        all_issues.extend(_lint_skill(skill_dir, args.project_root))

    if args.error_only:
        issues_to_show = [i for i in all_issues if i.severity == "ERROR"]
    else:
        issues_to_show = all_issues

    if not issues_to_show:
        print(f"Linted {len(skill_dirs)} skill(s) — no issues found")
        return 0

    for issue in issues_to_show:
        print(f"{issue.severity}  [{issue.rule}]  {issue.file}  {issue.message}")

    errors = [i for i in all_issues if i.severity == "ERROR"]
    warnings = [i for i in all_issues if i.severity == "WARNING"]
    print(f"\n{len(skill_dirs)} skill(s) linted — {len(errors)} error(s), {len(warnings)} warning(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
