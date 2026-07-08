# Distribution Guide

dcc-mcp-photoshop ships through three distribution channels, plus a
release-please based GitHub release workflow that produces all artifacts.

---

## Distribution Channels

| Channel | Artifact | Dependency | Use Case |
|---------|----------|------------|----------|
| PyPI | `dcc-mcp-photoshop` wheel + sdist | Python 3.8+ | Server-side MCP setup |
| GitHub Release | Standalone binary (Win/Linux/Mac) | None | Zero-Python deployment |
| GitHub Release | UXP `.ccx` plugin | Photoshop 2022+ | In-Photoshop bridge |
| Setup Skill | `photoshop-setup` (MCP skill) | Python 3.8+ | One-click guided install via AI agent |

### 1. PyPI (Python package)

```bash
pip install dcc-mcp-photoshop
```

Installs the `dcc-mcp-photoshop` Python package and the console-script entry
point. Requires Python and the `dcc-mcp-core` runtime dependency.

```bash
# Verify installation
dcc-mcp-photoshop --version

# Start the bridge plugin (requires external dcc-mcp-server)
dcc-mcp-photoshop

# Start embedded dev server (MCP HTTP + WS bridge in one process)
dcc-mcp-photoshop --embedded
```

### 2. Standalone binary

Each GitHub Release includes platform-specific binaries built with PyOxidizer.
No Python runtime required.

| Platform | Binary name | Architecture |
|----------|-------------|--------------|
| Windows | `dcc-mcp-photoshop-windows.exe` | x86_64 |
| Linux | `dcc-mcp-photoshop-linux` | x86_64 |
| macOS | `dcc-mcp-photoshop-macos` | x86_64 / arm64 |

```bash
# Download and run (example: Linux)
curl -L https://github.com/dcc-mcp/dcc-mcp-photoshop/releases/latest/download/dcc-mcp-photoshop-linux \
  -o dcc-mcp-photoshop
chmod +x dcc-mcp-photoshop
./dcc-mcp-photoshop --help
```

The binary includes the built-in skills and all dependencies. It accepts the
same flags as the Python entry point (`--mcp-port`, `--ws-port`, `--embedded`,
etc.).

### 3. UXP .ccx plugin

The UXP plugin runs inside Adobe Photoshop 2022+ and provides a WebSocket
server that the Python or binary bridge connects to.

**Install via Creative Cloud Desktop:**
1. Download the `.ccx` file from the GitHub Release (`dcc-mcp-photoshop-bridge-<version>.ccx`)
2. Open Creative Cloud Desktop → **Plugins** → **Manage Plugins**
3. Click the gear icon → **Install from file...**
4. Select the downloaded `.ccx` file
5. Restart Photoshop

**Install manually (Windows):**
```powershell
# Copy the .ccx to the system plugin directory
copy dcc-mcp-photoshop-bridge-<version>.ccx "$env:APPDATA\Adobe\UXP\Plugins\External\"
```

**Install manually (macOS):**
```bash
cp dcc-mcp-photoshop-bridge-<version>.ccx ~/Library/Application\ Support/Adobe/UXP/Plugins/External/
```

### 4. One-Click Installer (photoshop-setup skill)

The `photoshop-setup` MCP skill provides a guided installation workflow
driven by the AI agent. It is the recommended entry point for new users.

**Load the skill:**
```text
load_skill("photoshop-setup")
```

**Available tools:**

| Tool | Description |
|------|-------------|
| `check_environment` | Check system prerequisites |
| `install_package` | Install/upgrade the Python package via pip |
| `setup_uxp_plugin` | Install UXP .ccx plugin into Photoshop |
| `start_server` | Start server in dev mode |
| `verify_connection` | Verify bridge connection |
| `configure_mcp_client` | Auto-configure MCP client configs |

**Standard workflow:**

```text
check_environment → install_package → setup_uxp_plugin → configure_mcp_client → verify_connection
```

**Version pinning** — Install a specific version for compatibility:
```text
install_package(version="0.1.14")
```

**Upgrade** — Update to the latest PyPI release:
```text
install_package(upgrade=True)
```

**Rollback** — Revert to a previous version:
```text
install_package(version="0.1.13")
```

The skill lives in `src/dcc_mcp_photoshop/skills/photoshop-setup/` and
ships with the Python package and standalone binary.

---

## Getting from Release to Running Bridge

Complete workflow from downloading a release to having a working Photoshop MCP
bridge:

### Option A: PyPI + UXP plugin (recommended for development)

```bash
# 1. Install the Python package
pip install dcc-mcp-photoshop

# 2. Download the dcc-mcp-server binary from dcc-mcp-core releases
python tools/download_dcc_mcp_server.py

# 3. Download and install the .ccx plugin in Photoshop
#    (from GitHub Releases assets)

# 4. Start the standalone MCP server
./bin/dcc-mcp-server --dcc photoshop --mcp-port 8765 --skill-paths ./skills --no-bridge

# 5. Start the bridge plugin (connects to UXP WebSocket and MCP server)
dcc-mcp-photoshop
```

### Option B: Standalone binary (no Python, for deployment)

```bash
# 1. Download the platform binary and .ccx from GitHub Releases
# 2. Install the .ccx in Photoshop (see UXP section above)
# 3. Run both dcc-mcp-server.exe and the bridge binary from the sidecar directory

# Or use the UXP plugin's sidecar auto-launcher:
# The sidecar directory bundled with the .ccx contains start-sidecar.cmd
# which auto-launches dcc-mcp-server.exe + bridge binary.
```

### Option C: All-in-one with sidecar

When the UXP plugin is installed via the `.ccx`, the sidecar directory inside
the plugin includes launcher scripts that automatically start the MCP server
and bridge. See `bridge/uxp-plugin/sidecar/`.

---

## Version Compatibility Matrix

The following table shows which versions of each component work together:

| Photoshop Plugin (.ccx) | dcc-mcp-photoshop | dcc-mcp-core | Sidecar Binary |
|-------------------------|-------------------|--------------|----------------|
| current main | current main | >=0.19.17,<1.0.0 | dcc-mcp-server >=0.19.17 |
| 0.1.x through 0.1.26 | 0.1.x through 0.1.26 | >=0.12.14,<1.0.0 | dcc-mcp-server >=0.12.14 |
| 0.2.x | 0.2.x | >=0.18.14,<1.0.0 | dcc-mcp-server >=0.18.14 |

Version alignment rules:

- **UXP plugin version** must match the `dcc-mcp-photoshop` Python package
  version (they are released together from the same git tag).
- **dcc-mcp-photoshop** pins `dcc-mcp-core` within a major version range
  (see `pyproject.toml` `[project.dependencies]`).
- **Sidecar binary** (`dcc-mcp-server`) is downloaded from the matching
  `dcc-mcp-core` release during CI or via `tools/download_dcc_mcp_server.py`.
  Its version is determined by the installed `dcc-mcp-core` Python package.
- **`.ccx manifest.json`** carries the matched version number so Photoshop
  can validate compatibility at load time.

---

## Release Workflow

Releases are managed by [release-please](https://github.com/googleapis/release-please-action)
and the `.github/workflows/release.yml` pipeline.

### Automated release (push to main)

1. Conventional commit merge to `main` triggers release-please
2. release-please creates/updates a Release PR with changelog + version bumps
3. Merging the Release PR creates a git tag (`vX.Y.Z`) and triggers the build
4. Pipeline builds: wheel/sdist → PyPI publish → binary (3 platforms) → .ccx
5. All artifacts are attached to the GitHub Release

### Manual artifact rebuild (workflow_dispatch)

For rebuilding artifacts from an existing tag (e.g., after a CI infrastructure
fix):

1. Go to **Actions** → **Release** → **Run workflow**
2. Set `tag_name` to the existing tag (e.g., `v0.2.0`)
3. Set `release_version` to the version without prefix (e.g., `0.2.0`)
4. The pipeline checks out the tag, rebuilds all artifacts, and attaches them
   to the existing release

This does NOT publish to PyPI again or create a new release — it only
replaces the release assets.

### Artifact set per release

```
dcc-mcp-photoshop-<version>-py3-none-any.whl          # Python wheel
dcc-mcp-photoshop-<version>.tar.gz                       # Python sdist
dcc-mcp-photoshop-bridge-<version>.ccx                   # UXP plugin
dcc-mcp-photoshop-windows.exe                        # Windows binary
dcc-mcp-photoshop-linux                              # Linux binary
dcc-mcp-photoshop-macos                              # macOS binary
```

---

## Sidecar Directory Layout

When the UXP `.ccx` plugin is unpacked, the sidecar directory contains:

```
sidecar/
├── dcc-mcp-server.exe            # MCP core binary (platform-specific)
├── dcc-mcp-photoshop.exe         # Bridge binary (platform-specific)
├── server.log                    # Runtime log
├── logs/                         # Rotated log files
├── skills/                       # Photoshop skill scripts (YAML + Python)
├── start-sidecar.cmd             # Windows launcher
├── start-sidecar.vbs             # Windows hidden-window launcher
├── stop-sidecar.cmd              # Windows stopper
├── windows/
│   ├── dcc-mcp-server.exe
│   ├── start-sidecar.cmd
│   ├── start-sidecar.vbs
│   ├── stop-sidecar.cmd
│   └── stop-sidecar.vbs
```

> **Note:** `dcc-mcp-server.exe` is no longer committed to the repository. It is
> downloaded dynamically from [dcc-mcp-core GitHub Releases] during `stage_plugin_sidecar.py`
> or the CI pipeline. See `tools/download_dcc_mcp_server.py`.

The `start-sidecar.cmd` launcher:
1. Checks if a sidecar is already running on the configured ports
2. Probes `dcc-mcp-server.exe --help` to detect `--app` vs `--dcc` flag
3. Starts `dcc-mcp-server.exe` as a hidden background process
4. Redirects all output to `server.log`
