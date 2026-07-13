"""Dual-purpose entry point for the PyOxidizer standalone executable."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path
from typing import Sequence

from dcc_mcp_photoshop.cli import main as _cli_main

_PYTHON_SCRIPT_SUFFIXES = frozenset({".py", ".pyw"})


def _run_cli() -> None:
    _cli_main()


def _is_skill_script_invocation(argv: Sequence[str]) -> bool:
    if len(argv) < 2:
        return False
    script = Path(argv[1])
    return script.suffix.lower() in _PYTHON_SCRIPT_SUFFIXES and script.is_file()


def _run_skill_script(argv: Sequence[str]) -> None:
    script = str(Path(argv[1]).resolve())
    original_argv = sys.argv
    sys.argv = [script, *argv[2:]]
    try:
        runpy.run_path(script, run_name="__main__")
    finally:
        sys.argv = original_argv


def main(argv: Sequence[str] | None = None) -> None:
    """Run the adapter CLI or execute a core-managed Python skill script."""
    resolved_argv = list(sys.argv if argv is None else argv)
    os.environ.setdefault("DCC_MCP_PYTHON_EXECUTABLE", sys.executable)
    if _is_skill_script_invocation(resolved_argv):
        _run_skill_script(resolved_argv)
        return
    _run_cli()


if __name__ == "__main__":
    main()
