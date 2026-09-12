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

Compatibility and diagnostics skill for dcc-mcp-photoshop. The canonical
installer is `dcc-mcp-photoshop install --json`; this skill must not create a
second staging, receipt, rollback, or uninstall implementation.

## Distribution Channels

| Channel | Command / Artifact | Python Required |
|---------|-------------------|-----------------|
| **pip** | `pip install dcc-mcp-photoshop` | Yes |
| **Standalone binary** | GitHub Releases — platform-specific binary | No |
| **adobepy bridge** | Managed by `dcc-mcp-photoshop install --json` | No |

## Workflow

1. Run `dcc-mcp-cli doctor` to inspect the local CLI and gateway.
2. For an Internal deployment with an approved prebuilt bridge, run
   `dcc-mcp-cli install --dcc-type photoshop` with the bridge root in
   `--plugin-source` and the Adobe debug root in `--adobe-debug-root`.
   Profiles may provide `DCC_MCP_PLUGIN_SOURCE` and
   `DCC_MCP_ADOBE_DEBUG_ROOT`. Otherwise use the adapter-owned
   `dcc-mcp-photoshop install --json` lifecycle.
3. Review and execute the adapter-owned plan when provisioning or generating a
   bridge: `dcc-mcp-photoshop install --json --dry-run`, then
   `dcc-mcp-photoshop install --json --yes`.
4. Run `dcc-mcp-cli list` and
   `dcc-mcp-cli wait-ready --dcc-type photoshop`, then
   `dcc-mcp-photoshop verify --json`; only a real Photoshop RPC is usable.

The shared CLI links an approved bridge but does not copy files or invoke UXP
Developer Tool. A link on disk is not proof that Photoshop loaded the bridge.

## Tools

- `check_environment` — Python / pip / installed packages / Photoshop process / adobepy broker
- `install_package` — pip install dcc-mcp-photoshop
- `setup_uxp_plugin` — Legacy compatibility redirect to the canonical CLI
- `start_server` — Start the MCP adapter after the adobepy broker is ready
- `verify_connection` — End-to-end connection check
- `configure_mcp_client` — Write MCP client config for Claude Desktop / Cursor / VS Code
