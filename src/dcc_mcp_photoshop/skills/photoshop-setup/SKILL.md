---
name: photoshop-setup
description: "Adobe Photoshop MCP setup — install, configure, and verify the dcc-mcp-photoshop bridge, UXP plugin, and server connection"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, setup, install, configure, bridge, uxp, adobe]
search-hint: "install setup configure bridge uxp plugin server verify photoshop mcp"
license: "MIT"
allowed-tools: ["Bash", "Read", "Write"]
depends: []
tools:
  - name: check_environment
    description: "Check system prerequisites: Python version, pip, installed packages, Photoshop and UXP plugin status."
    source_file: scripts/check_environment.py
    read_only: true
    destructive: false
    idempotent: true
  - name: install_package
    description: "Install or upgrade dcc-mcp-photoshop and its dependencies via pip."
    source_file: scripts/install_package.py
    read_only: false
    destructive: false
    idempotent: true
  - name: setup_uxp_plugin
    description: "Install the UXP .ccx plugin into Photoshop — download, install via Creative Cloud or manual copy."
    source_file: scripts/setup_uxp_plugin.py
    read_only: false
    destructive: false
    idempotent: true
  - name: start_server
    description: "Start the dcc-mcp-photoshop server in embedded mode for development and testing."
    source_file: scripts/start_server.py
    read_only: false
    destructive: false
    idempotent: false
  - name: verify_connection
    description: "Verify the full bridge connection: Photoshop UXP plugin reachable, server responding, skills discoverable."
    source_file: scripts/verify_connection.py
    read_only: true
    destructive: false
    idempotent: true
---

# photoshop-setup

Guided setup skill for dcc-mcp-photoshop. Helps agents walk through the entire
installation, configuration, and verification flow.

## Distribution Channels

| Channel | Command / Artifact | Python Required |
|---------|-------------------|-----------------|
| **pip** | `pip install dcc-mcp-photoshop` | Yes |
| **Standalone binary** | GitHub Releases — platform-specific binary | No |
| **UXP .ccx plugin** | GitHub Releases — install into Photoshop | No |

## Workflow

1. **check_environment** — Inspect the current system state
2. **install_package** — Install dcc-mcp-photoshop via pip (or skip if using binary)
3. **setup_uxp_plugin** — Install the UXP .ccx plugin in Photoshop
4. **start_server** — Launch the MCP server (embedded mode)
5. **verify_connection** — Confirm everything is working

## Tools

- `check_environment` — Python / pip / installed packages / Photoshop process / UXP port
- `install_package` — pip install dcc-mcp-photoshop
- `setup_uxp_plugin` — Download and install the .ccx plugin
- `start_server` — Start embedded MCP server + bridge
- `verify_connection` — End-to-end connection check
