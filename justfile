# dcc-mcp-photoshop justfile
# Requires: https://github.com/casey/just
#
# Quick reference:
#   just              — list all available commands
#   just test         — run Python tests
#   just lint         — run ruff checks
#   just lint-skills  — lint SKILL.md files
#   just dev          — install package in editable/dev mode

# Use cmd.exe on Windows so just works without Git Bash in PATH
set windows-shell := ["cmd.exe", "/c"]

# Default: list all commands
default:
    @just --list

# ── Development ───────────────────────────────────────────────────────────────

# Install the Python package in editable mode with dev dependencies
dev:
    pip install -e ".[dev]"

# Run the Python test suite
test:
    pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
    pytest tests/ -v --tb=short --cov=src/dcc_mcp_photoshop --cov-report=term-missing

# ── Lint & format ─────────────────────────────────────────────────────────────

# Run ruff lint check
lint:
    ruff check src/ tests/

# Run ruff format check (no changes)
lint-format:
    ruff format --check src/ tests/

# Auto-fix ruff lint issues
fix:
    ruff check --fix src/ tests/

# Auto-format code
format:
    ruff format src/ tests/

# Lint SKILL.md files
lint-skills:
    python tools/lint_skills.py

# Run all lint checks (no auto-fix)
lint-all: lint lint-format lint-skills

# ── Build ─────────────────────────────────────────────────────────────────────

# Build the Python wheel and sdist
build:
    python -m build

# Build the standalone binary (dcc-mcp-photoshop.exe / dcc-mcp-photoshop)
# Zero Python dependency for end users — distribute alongside the UXP plugin
build-binary:
    python tools/build_binary.py

# Build binary as directory (faster startup, easier to inspect)
build-binary-dir:
    python tools/build_binary.py --onedir

# Build everything owned by this repository
build-all: build build-binary
    @echo "Build complete — see dist/"

# ── Run server ────────────────────────────────────────────────────────────────

# Python executable — override with: just python="python3.12" serve
python := "uv run python"

# Start the broker-backed MCP adapter
serve:
    {{python}} -m dcc_mcp_photoshop

# Start with custom ports
serve-ports mcp_port="0" gateway_port="9765":
    {{python}} -m dcc_mcp_photoshop --mcp-port {{mcp_port}} --gateway-port {{gateway_port}}

# Clean all build artifacts
clean:
    python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['dist', 'build', 'src/dcc_mcp_photoshop.egg-info']]"
    @echo "Cleaned dist/, build/, and egg-info"

# ── CI helpers ────────────────────────────────────────────────────────────────

# Run all checks (equivalent to CI: test + lint + lint-skills)
ci: test lint-all
    @echo "All CI checks passed"
