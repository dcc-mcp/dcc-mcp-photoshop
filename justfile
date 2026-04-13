# dcc-mcp-photoshop justfile
# Requires: https://github.com/casey/just
#
# Quick reference:
#   just              — list all available commands
#   just pack-plugin  — build the .ccx UXP plugin
#   just install-plugin — install plugin to Photoshop (Windows/macOS)
#   just test         — run Python tests
#   just lint         — run ruff checks
#   just lint-skills  — lint SKILL.md files
#   just dev          — install package in editable/dev mode

# Default: list all commands
default:
    @just --list

# ── Plugin packaging ──────────────────────────────────────────────────────────

# Pack the UXP plugin into a .ccx archive (output: dist/plugin/)
pack-plugin:
    python tools/pack_plugin.py

# Pack with a specific version
pack-plugin-version version:
    python tools/pack_plugin.py --version {{version}}

# Pack and open the output directory
pack-plugin-open: pack-plugin
    {{ if os() == "windows" { "explorer dist\\plugin" } else if os() == "macos" { "open dist/plugin" } else { "xdg-open dist/plugin" } }}

# ── Plugin installation ───────────────────────────────────────────────────────

# Install the UXP plugin for development via junction (Windows) or symlink (macOS)
# Windows path: %APPDATA%\Adobe\UXP\Plugins\External\com.dcc-mcp.photoshop-bridge
# macOS path:   ~/Library/Application Support/Adobe/UXP/Plugins/External/com.dcc-mcp.photoshop-bridge
install-plugin-dev:
    @echo "Installing UXP plugin for development..."
    python tools/install_plugin_dev.py
    @echo "Done. Restart Photoshop to load the plugin."

# Copy the packed .ccx to the system plugin install directory
# (requires Creative Cloud Desktop App to be running)
install-plugin: pack-plugin
    {{ if os() == "windows" { \
        "python -c \"import pathlib, shutil, glob; files=glob.glob('dist/plugin/*.ccx'); f=files[0] if files else None; dst=pathlib.Path(input('Install path: ')); print(f'Copy {f} -> {dst}'); shutil.copy(f, dst)\" " \
    } else if os() == "macos" { \
        "python -c \"import pathlib, shutil, glob; files=glob.glob('dist/plugin/*.ccx'); f=files[0] if files else None; print(f'CCX file: {f}'); print('To install: open dist/plugin/ and double-click the .ccx file')\" " \
    } else { \
        "echo 'Linux is not supported by Adobe Photoshop'" \
    } }}

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

# Build everything: Python wheel + UXP plugin + standalone binary
build-all: build pack-plugin build-binary
    @echo "Build complete — see dist/"

# ── Run server ────────────────────────────────────────────────────────────────

# Start the MCP + WebSocket bridge server (dev mode, uses installed package)
serve:
    python -m dcc_mcp_photoshop

# Start with custom ports
serve-ports mcp_port="8765" ws_port="9001":
    python -m dcc_mcp_photoshop --mcp-port {{mcp_port}} --ws-port {{ws_port}}

# Clean all build artifacts
clean:
    python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['dist', 'build', 'src/dcc_mcp_photoshop.egg-info']]"
    @echo "Cleaned dist/, build/, and egg-info"

# ── CI helpers ────────────────────────────────────────────────────────────────

# Run all checks (equivalent to CI: test + lint + lint-skills)
ci: test lint-all
    @echo "All CI checks passed"
