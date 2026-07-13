---
name: photoshop-setup
description: Adobe Photoshop MCP setup — stage and load the adobepy UXP bridge, configure clients, and verify the full server
  connection
license: MIT
allowed-tools:
- Bash
- Read
- Write
metadata:
  dcc-mcp:
    dcc: photoshop
    version: 0.1.0
    layer: infrastructure
    tags:
    - photoshop
    - setup
    - install
    - configure
    - bridge
    - uxp
    - adobe
    search-hint: install setup configure bridge uxp plugin server verify photoshop mcp
    tools: tools.yaml
---
# photoshop-setup

Guided setup skill for dcc-mcp-photoshop. Helps agents walk through the entire
installation, configuration, and verification flow.

## Distribution Channels

| Channel | Command / Artifact | Python Required |
|---------|-------------------|-----------------|
| **pip** | `pip install dcc-mcp-photoshop` | Yes |
| **Standalone binary** | GitHub Releases — platform-specific binary | No |
| **adobepy bridge** | `adobepy install-bridge photoshop --dest <dir>` | No |

## Workflow

1. **check_environment** — Inspect the current system state
2. **install_package** — Install dcc-mcp-photoshop via pip
3. **setup_uxp_plugin** — Stage the adobepy UXP bridge, then load it with Adobe UXP Developer Tool
4. **start_server** — Launch the broker-backed MCP adapter
5. **verify_connection** — Confirm everything is working
6. **configure_mcp_client** — Auto-configure Claude Desktop / Cursor / VS Code with the gateway URL

## Tools

- `check_environment` — Python / pip / installed packages / Photoshop process / adobepy broker
- `install_package` — pip install dcc-mcp-photoshop
- `setup_uxp_plugin` — Generate bridge files without falsely claiming Adobe loaded them
- `start_server` — Start the MCP adapter after the adobepy broker is ready
- `verify_connection` — End-to-end connection check
- `configure_mcp_client` — Write MCP client config for Claude Desktop / Cursor / VS Code
