from __future__ import annotations

import json
import sys
from pathlib import Path

from dcc_mcp_photoshop import _standalone_entry


def test_project_requires_core_with_stdin_parameter_forwarding():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert '"dcc-mcp-core>=0.19.32,<1.0.0"' in pyproject


def test_server_invocation_delegates_to_cli(monkeypatch):
    called = []
    monkeypatch.setattr(_standalone_entry, "_run_cli", lambda: called.append(True))

    _standalone_entry.main(["dcc-mcp-photoshop", "--version"])

    assert called == [True]


def test_skill_invocation_runs_script_with_embedded_interpreter(tmp_path, monkeypatch, capsys):
    script = tmp_path / "skill.py"
    script.write_text(
        "import json, os, sys\n"
        "print(json.dumps({'argv': sys.argv, 'python': os.environ['DCC_MCP_PYTHON_EXECUTABLE']}))\n",
        encoding="utf-8",
    )
    executable = str(tmp_path / "dcc-mcp-photoshop.exe")
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.delenv("DCC_MCP_PYTHON_EXECUTABLE", raising=False)

    _standalone_entry.main([executable, str(script), "--include-hidden", "false"])

    output = json.loads(capsys.readouterr().out)
    assert output["python"] == executable
    assert output["argv"] == [str(script), "--include-hidden", "false"]
