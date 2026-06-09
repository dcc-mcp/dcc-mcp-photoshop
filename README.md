# dcc-mcp-photoshop

Bring Adobe Photoshop to MCP-native AI agents.

`dcc-mcp-photoshop` turns Photoshop into a standards-compliant **MCP Streamable HTTP** backend via a UXP WebSocket plugin. Agents can inspect documents, create and edit layers, apply text, export images, and automate Photoshop workflows through typed tools instead of brittle ad-hoc scripts.

The Python bridge runs a WebSocket server that the UXP plugin connects to as a client (UXP only supports WS client mode). All Photoshop automation goes through the [adobepy](https://github.com/dcc-mcp/adobepy) facade layer, which abstracts over the WebSocket bridge.

[![CI](https://github.com/dcc-mcp/dcc-mcp-photoshop/actions/workflows/ci.yml/badge.svg)](https://github.com/dcc-mcp/dcc-mcp-photoshop/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/dcc-mcp/dcc-mcp-photoshop/graph/badge.svg)](https://codecov.io/gh/dcc-mcp/dcc-mcp-photoshop)
[![GitHub release](https://img.shields.io/github/v/release/dcc-mcp/dcc-mcp-photoshop?label=release)](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)
[![GitHub release date](https://img.shields.io/github/release-date/dcc-mcp/dcc-mcp-photoshop?label=released)](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)
[![Last commit](https://img.shields.io/github/last-commit/dcc-mcp/dcc-mcp-photoshop?label=last%20commit)](https://github.com/dcc-mcp/dcc-mcp-photoshop/commits/main/)
[![Issues](https://img.shields.io/github/issues/dcc-mcp/dcc-mcp-photoshop?label=issues)](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/dcc-mcp/dcc-mcp-photoshop?label=PRs)](https://github.com/dcc-mcp/dcc-mcp-photoshop/pulls)
[![PyPI](https://img.shields.io/pypi/v/dcc-mcp-photoshop?label=PyPI)](https://pypi.org/project/dcc-mcp-photoshop/)
[![PyPI downloads](https://img.shields.io/pypi/dm/dcc-mcp-photoshop?label=downloads%2Fmonth)](https://pypistats.org/packages/dcc-mcp-photoshop)
[![Downloads](https://static.pepy.tech/badge/dcc-mcp-photoshop)](https://pepy.tech/project/dcc-mcp-photoshop)
[![Python](https://img.shields.io/pypi/pyversions/dcc-mcp-photoshop?label=Python)](https://pypi.org/project/dcc-mcp-photoshop/)
[![Photoshop](https://img.shields.io/badge/Photoshop-2022%2B-001E36)](https://www.adobe.com/products/photoshop.html)
[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-6f42c1)](https://modelcontextprotocol.io/)
[![dcc-mcp-core](https://img.shields.io/badge/dcc--mcp--core-%3E%3D0.18.14-blue)](https://github.com/dcc-mcp/dcc-mcp-core)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Why Use It

| What you get | Why it matters |
|---|---|
| **20+ typed Photoshop tools** across 4 bundled skill packages | Agents can call validated tools for document, layer, image, and text operations. |
| **Native UXP plugin** | Communicates with Photoshop through the official UXP API — no deprecated ExtendScript bridges. |
| **Sidecar isolation** | Python bridge runs outside Photoshop's UI thread; the UXP plugin connects as a WebSocket client. |
| **Gateway compatible** | Works with `dcc-mcp-server` sidecar for multi-DCC deployments alongside Maya, Houdini, Blender, etc. |
| **Multi-channel distribution** | Available as PyPI package, standalone binary (no Python runtime), or UXP `.ccx` plugin. |
| **One-click setup** | The `photoshop-setup` skill automates environment checks, plugin installation, and MCP client configuration. |

## Quick Start

### 1. Download & Install the UXP plugin

Download the latest `.ccx` from [GitHub Releases](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases), install via Creative Cloud Desktop, and restart Photoshop.

The plugin automatically starts the bundled sidecar (bridge + MCP server) when Photoshop loads.

### 2. Configure your MCP client

Point your MCP client to the **gateway URL**. The gateway auto-discovers which DCC (Photoshop, Maya, etc.) to route each tool call to, so you only need one endpoint:

```json
{
  "mcpServers": {
    "photoshop": {
      "url": "http://127.0.0.1:9765/mcp"
    }
  }
}
```

### 3. Smoke test

```text
Search for Photoshop tools, load the photoshop-document skill, and list layers in the current document.
```

## Architecture

```
AI Agent (Claude Desktop / Cursor / Copilot)
    │  MCP Streamable HTTP (gateway port 9765)
    ▼
dcc-mcp-server Gateway
    │  auto-discovers DCC via capability index
    ▼
PhotoshopMcpServer  [Python sidecar]
    │  WebSocket JSON-RPC (port 9001)
    ▼
UXP Plugin  [bridge/uxp-plugin/, JavaScript]
    │  Photoshop UXP API
    ▼
Adobe Photoshop 2022+
```

**Key architectural decisions:**
- Python runs a **WebSocket server** on port 9001; the UXP plugin connects to it as a **WebSocket client** (UXP only supports WS client mode).
- The MCP server (HTTP on port 8765) and the WebSocket bridge can run in the same process (embedded, dev only) or separately (gateway mode, recommended for deployment).
- All Photoshop automation goes through the [adobepy](https://github.com/dcc-mcp/adobepy) facade layer, which abstracts over the WebSocket bridge.
- UXP plugin features exponential back-off reconnect, persistent logging, and a panel UI showing connection status.

## Tool Surface

Skills are **lazy-loaded**: only meta-tools are available initially. Use `load_skill` to expand:

```
search_skills / dcc_capability_manifest
  -> load_skill("photoshop-document")
  -> list_layers(...)
```

### photoshop-document

Document information and layer listing.

| Tool | Description | Read-only |
|------|-------------|-----------|
| `get_document_info` | Get metadata about the active Photoshop document (name, size, resolution, color mode) | ✅ |
| `list_layers` | List all layers in the active document. Set `include_hidden=false` to exclude hidden layers | ✅ |

### photoshop-image

Document creation, export, canvas/image resize, flatten, and merge operations.

| Tool | Description | Read-only |
|------|-------------|-----------|
| `create_document` | Create a new document with specified dimensions, resolution and color mode | ❌ |
| `export_document` | Export the active document to PNG, JPG, TIFF, or PSD | ❌ |
| `save_document` | Save the active document in its current format | ❌ |
| `resize_canvas` | Resize canvas without scaling content | ❌ |
| `resize_image` | Scale the image (resamples content) | ❌ |
| `flatten_image` | Flatten all layers into a single background layer | ❌ |
| `merge_visible_layers` | Merge all visible layers | ❌ |

### photoshop-layers

Full CRUD for layers plus visual property changes.

| Tool | Description | Read-only |
|------|-------------|-----------|
| `create_layer` | Create a pixel, group, or adjustment layer | ❌ |
| `delete_layer` | Delete a named layer | ❌ |
| `duplicate_layer` | Duplicate a named layer | ❌ |
| `rename_layer` | Rename a layer | ❌ |
| `set_layer_opacity` | Set opacity (0-100) of a named layer | ❌ |
| `set_layer_visibility` | Show or hide a named layer | ❌ |
| `set_layer_blend_mode` | Set blend mode (normal, multiply, screen, overlay, etc., 27 modes) | ❌ |
| `fill_layer` | Fill a layer with solid color (hex) or transparent | ❌ |

### photoshop-text

Text layer creation, editing, and inspection.

| Tool | Description | Read-only |
|------|-------------|-----------|
| `create_text_layer` | Create a new text layer with content and styling (font, size, color, alignment) | ❌ |
| `update_text_layer` | Update text content or style of an existing text layer | ❌ |
| `get_text_layer_info` | Get text content and style properties of a text layer | ✅ |

## Runtime Features

| Feature | Surface |
|---|---|
| Capability manifest | `dcc_capability_manifest({"loaded_only": false})` returns a compact index of loaded and unloaded Photoshop skills. |
| UXP plugin reconnect | Exponential back-off: 3s → 6s → 12s → ... → 60s maximum. |
| Persistent logging | Bridge log written to UXP PluginData directory (`bridge.log`). |
| Connection UI | Panel shows Connected / Disconnected / Connecting status with manual connect/disconnect. |
| Cross-process RPC | HTTP RPC server on port 9100 for gateway mode inter-process bridge access. |
| Lazy skill loading | `load_skill` meta-tool expands the tool surface on demand. |

## One-Click Setup

```
load_skill("photoshop-setup")
```

| Tool | Description |
|------|-------------|
| `check_environment` | Check system prerequisites |
| `install_package` | Install via pip |
| `setup_uxp_plugin` | Install UXP .ccx plugin |
| `start_server` | Start server (dev mode) |
| `verify_connection` | Verify bridge connection |
| `configure_mcp_client` | Auto-configure MCP client configs for Claude Desktop, Cursor, VS Code |

## Installation

### PyPI

```bash
pip install dcc-mcp-photoshop
```

Install with sidecar dependencies (recommended for the default plugin gateway mode):

```bash
pip install "dcc-mcp-photoshop[sidecar]"
```

Or via `uvx`:

```bash
uvx --with dcc-mcp-photoshop dcc-mcp-photoshop --embedded
```

From source:

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-photoshop.git
cd dcc-mcp-photoshop
pip install -e ".[dev]"
```

### Standalone Binary

Each [GitHub Release](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases) includes platform-specific binaries built with PyInstaller. No Python runtime required.

| Platform | Binary name |
|----------|-------------|
| Windows | `dcc-mcp-photoshop-windows.exe` |
| Linux | `dcc-mcp-photoshop-linux` |
| macOS | `dcc-mcp-photoshop-macos` |

```bash
curl -L https://github.com/dcc-mcp/dcc-mcp-photoshop/releases/download/v0.1.6/dcc-mcp-photoshop-linux \
  -o dcc-mcp-photoshop
chmod +x dcc-mcp-photoshop
./dcc-mcp-photoshop --help
```

### UXP .ccx Plugin

Install the `.ccx` into Photoshop if you only need the UXP sidecar:

1. Download the `.ccx` from the [latest release assets](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)
2. Open **Creative Cloud Desktop** → **Plugins** → **Manage Plugins**
3. Click the gear icon → **Install from file...**
4. Select the downloaded `.ccx` file
5. Restart Photoshop

Manual install:

```powershell
# Windows
copy dcc-mcp-photoshop-bridge-*.ccx "$env:APPDATA\Adobe\UXP\Plugins\External\"
```

```bash
# macOS
cp dcc-mcp-photoshop-bridge-*.ccx ~/Library/Application\ Support/Adobe/UXP/Plugins/External/
```

## Configuration

### MCP Client Configuration

#### Claude Desktop

```json
{
  "mcpServers": {
    "photoshop": {
      "url": "http://127.0.0.1:9765/mcp"
    }
  }
}
```

The gateway URL (`:9765`) is a unified facade that aggregates tools from all registered DCCs. On `tools/call`, the gateway auto-discovers the correct DCC instance via the capability index — no need to specify the DCC type in the URL.

Embedded mode via command:

```json
{
  "mcpServers": {
    "photoshop": {
      "command": "dcc-mcp-photoshop",
      "args": ["--embedded"],
      "env": {}
    }
  }
}
```

#### Cursor

In Cursor Settings → Features → MCP Servers:

```
Name: photoshop
Type: url
URL: http://127.0.0.1:9765/mcp
```

#### VS Code (via MCP extension)

```json
{
  "mcp": {
    "servers": {
      "photoshop": {
        "command": "dcc-mcp-photoshop",
        "args": ["--embedded"]
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DCC_MCP_REGISTRY_DIR` | Shared FileRegistry directory for gateway discovery | `~/.dcc-mcp/registry` |
| `DCC_MCP_PHOTOSHOP_SKILL_PATHS` | Extra skill directories (colon-separated) | — |
| `DCC_MCP_SKILL_PATHS` | Global extra skill directories | — |
| `DCC_MCP_GATEWAY_PORT` | Gateway competition port | `9765` |

## Bridge Protocol

The Python ↔ UXP communication uses JSON-RPC 2.0 over a WebSocket connection. Python is the server (port 9001); the UXP plugin connects as a client.

### Handshake

On connection, the UXP plugin sends a `hello` message:

```json
{
  "type": "hello",
  "protocol": "photoshop-bridge",
  "version": "0.1.0",
  "client": "photoshop-uxp",
  "reconnect": false
}
```

Python responds with `hello_ack`:

```json
{
  "type": "hello_ack",
  "protocol": "photoshop-bridge",
  "version": "0.1.0"
}
```

### RPC lifecycle

**Python → UXP:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "ps.listLayers",
  "params": {"include_hidden": true}
}
```

**UXP → Python (success):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [
    {"name": "Background", "type": "pixel", "visible": true, "opacity": 100}
  ]
}
```

**UXP → Python (error):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {"code": -32603, "message": "No active document", "hint": "Open a document first"}
}
```

**Progress notifications (UXP → Python):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "type": "progress",
  "progress": {"current": 50, "total": 100, "message": "Exporting..."}
}
```

### Supported RPC Methods

| Method | Description |
|--------|-------------|
| `ps.getDocumentInfo` | Get active document metadata |
| `ps.listDocuments` | List all open documents |
| `ps.createDocument` | Create a new document |
| `ps.saveDocument` | Save the active document |
| `ps.closeDocument` | Close a document |
| `ps.exportDocument` | Export to PNG/JPG/TIFF/PSD |
| `ps.resizeCanvas` | Resize canvas |
| `ps.resizeImage` | Scale image (resample) |
| `ps.flattenImage` | Flatten all layers |
| `ps.mergeVisibleLayers` | Merge visible layers |
| `ps.listLayers` | List layers |
| `ps.createLayer` | Create a pixel/group/adjustment layer |
| `ps.deleteLayer` | Delete a layer by name |
| `ps.setLayerVisibility` | Show/hide a layer |
| `ps.renameLayer` | Rename a layer |
| `ps.setLayerOpacity` | Set layer opacity (0-100) |
| `ps.duplicateLayer` | Duplicate a layer |
| `ps.setLayerBlendMode` | Set blend mode |
| `ps.fillLayer` | Fill with solid color |
| `ps.createTextLayer` | Create a text layer |
| `ps.updateTextLayer` | Update text content/style |
| `ps.getTextLayerInfo` | Get text layer properties |
| `ps.executeScript` | Execute JS expression (limited) |
| `ps.executeAction` | Execute a Photoshop action |

## Skill Authoring

There are two approaches to authoring Photoshop skills:

### New-style (adobepy facade, recommended)

```python
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def list_layers(**kwargs) -> dict:
    """List all layers in the active Photoshop document."""
    app = Photoshop()
    return action_result(
        "Listed active Photoshop layers",
        lambda: {"layers": [layer.name for layer in app.activeLayers]},
        prompt="Use the layer names in the next Photoshop operation.",
    )


def main(**kwargs):
    return list_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
```

### Legacy-style (direct bridge access, deprecated)

```python
from dcc_mcp_core.skill import skill_entry
from dcc_mcp_photoshop.api import get_bridge, with_photoshop, ps_success


@skill_entry
@with_photoshop
def list_layers(**kwargs) -> dict:
    """List all layers in a Photoshop document."""
    bridge = get_bridge()
    layers = bridge.call("ps.listLayers")
    return ps_success(
        f"Found {len(layers)} layer(s)",
        layers=[layer["name"] for layer in layers],
    )
```

### Skill directory structure

```
skills/
├── photoshop-document/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
│       ├── get_document_info.py
│       └── list_layers.py
├── photoshop-image/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
├── photoshop-layers/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
├── photoshop-text/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
```

### Setting custom skill paths

```bash
export DCC_MCP_PHOTOSHOP_SKILL_PATHS=/path/to/my/skills
dcc-mcp-photoshop --embedded --skill-paths /path/to/my/skills
```

## CLI Reference

```
dcc-mcp-photoshop [OPTIONS]

Options:
  --embedded          Embedded mode: MCP server + bridge in one process (dev only)
  --mcp-port PORT     MCP HTTP server port (embedded mode; default: 8765)
  --ws-port PORT      WebSocket bridge port for UXP plugin (default: 9001)
  --ws-host HOST      WebSocket bind host (default: localhost)
  --rpc-port PORT     HTTP RPC server port for cross-process bridge access (default: 9100)
  --gateway-port PORT Gateway competition port (embedded mode; default: 9765)
  --server-name NAME  Server name reported in MCP initialize (default: photoshop-mcp)
  --skill-paths PATH  Extra skill directories
  --no-builtins       Do not discover built-in skills
  --verbose, -v       Enable debug logging
  --version           Show version and exit
```

## Python API

```python
import dcc_mcp_photoshop

handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=9001)
print(f"MCP URL: {handle.mcp_url()}")

# ... use with Claude Desktop, Cursor, etc.

handle.shutdown()
```

## Gateway Mode (Recommended for Deployment)

This mode uses the standalone `dcc-mcp-server` for the MCP server and `dcc-mcp-photoshop` as a lightweight bridge plugin.

**Terminal 1** — Start the MCP server (Rust binary, no Python needed):

```bash
dcc-mcp-server --dcc photoshop --mcp-port 8765 \
  --skill-paths ./skills --no-bridge \
  --gateway-port 9765 --registry-dir ~/.dcc-mcp/registry
```

**Terminal 2** — Start the bridge plugin:

```bash
python -m dcc_mcp_photoshop
```

**MCP clients** connect to the gateway URL:
- `http://127.0.0.1:9765/mcp` — **Gateway proxy (recommended)**: unified facade for all DCCs, auto-discovers the correct DCC on each call
- `http://127.0.0.1:8765/mcp` — Direct access (useful for debugging or single-DCC setups)

The gateway `/mcp` endpoint aggregates tools from ALL registered DCCs (Maya, Houdini, Blender, Photoshop, etc.). On `tools/call`, the gateway auto-discovers the correct DCC instance via the capability index.

## UXP Plugin Setup (Development)

The UXP plugin lives at `bridge/uxp-plugin/`. To load from source in Photoshop:

1. Open Photoshop
2. Go to **Plugins** → **Development** → **Load Plugin...**
3. Navigate to `bridge/uxp-plugin/` and select `manifest.json`
4. The plugin appears in the Plugins panel as "dcc-mcp Bridge"

### Plugin manifest

`bridge/uxp-plugin/manifest.json` declares:

| Field | Value |
|-------|-------|
| Plugin ID | `com.dcc-mcp.photoshop-bridge` |
| Name | `dcc-mcp Bridge` |
| Host app | Photoshop (PS) |
| Min version | Photoshop 2022 (22.0.0) |
| Network permissions | All domains |

## Development

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-photoshop.git
cd dcc-mcp-photoshop
pip install -e ".[dev]"
pytest tests/
```

## Requirements

- **Photoshop**: Adobe Photoshop 2022+ (UXP support required)
- **Python** (pip path only): Python 3.8+
- **Dependencies** (auto-installed with pip):
  - `dcc-mcp-core >= 0.18.14, < 1.0.0`
  - `adobepy >= 0.1.0`
  - `websockets >= 12.0`

| Path | Photoshop Required? | Python Required? |
|------|-------------------|-----------------|
| pip install | Yes (UXP plugin) | Yes |
| Standalone binary | Yes (UXP plugin) | No |
| UXP .ccx plugin only | Yes | No (bridge binary only) |

## Version Compatibility

| dcc-mcp-photoshop | dcc-mcp-core | UXP Plugin | Sidecar Binary |
|-------------------|-------------|------------|----------------|
| 0.1.x | >=0.12.14,<1.0.0 | 0.1.x | dcc-mcp-server >=0.12.14 |
| 0.2.x (planned) | >=0.18.2,<1.0.0 | 0.2.x | dcc-mcp-server >=0.18.2 |

## Distribution

Release artifacts per version:
- `dcc-mcp-photoshop-<version>-py3-none-any.whl` — Python wheel
- `dcc-mcp-photoshop-<version>.tar.gz` — Python sdist
- `dcc-mcp-photoshop-bridge-<version>.ccx` — UXP plugin
- `dcc-mcp-photoshop-windows.exe` — Windows binary
- `dcc-mcp-photoshop-linux` — Linux binary
- `dcc-mcp-photoshop-macos` — macOS binary

## Roadmap

### v0.1.0 — Foundation ✅
- Package structure and API design
- PhotoshopBridge WebSocket client scaffold
- Skill authoring helpers
- UXP plugin architecture design

### v0.2.0 — UXP Plugin + Bridge ✅
- UXP plugin WebSocket client (JavaScript)
- Python bridge WebSocket server
- JSON-RPC 2.0 protocol implementation
- Release distribution (pip, binary, .ccx)
- 20+ Photoshop skills
- Cross-process RPC bridge

### v0.3.0 — Skills & Polish (next)
- Smart Object support
- Selection tools (marquee, magic wand)
- Filter application (blur, sharpen, etc.)
- Color adjustments (levels, curves, hue/saturation)
- Batch processing

### v1.0.0 — Production Ready
- Photoshop 2025+ UXP API compatibility
- Performance optimizations
- Authentication and security hardening

## Troubleshooting

### UXP plugin does not connect

1. Ensure Photoshop 2022+ is running
2. Check the plugin is loaded: **Plugins** → **Development** → **Load Plugin...** → select `manifest.json`
3. Verify the panel shows "Connected" status
4. Check the bridge log file at `~/.dcc-mcp/logs/photoshop-bridge.log`

### WebSocket connection refused

```
PhotoshopBridge could not connect to ws://localhost:9001 — skill calls will
fail until the Photoshop UXP plugin is running
```

1. Start the Python bridge first: `dcc-mcp-photoshop --embedded`
2. Then load the UXP plugin in Photoshop (or restart Photoshop with the plugin enabled)
3. The UXP plugin auto-connects to `ws://localhost:9001`

### No active document error

If skills return "No active document":
1. Open a document in Photoshop (File → New or File → Open)
2. Wait for the bridge status to show the document name
3. Retry the skill call

### Firewall blocking ports

Default ports used:
- `8765` — MCP HTTP server
- `9001` — WebSocket bridge (Python ↔ UXP)
- `9100` — HTTP RPC server
- `9765` — Gateway competition port

## Contributing

Contributions are especially welcome from those with:
- Adobe UXP / ExtendScript experience
- Photoshop automation knowledge
- WebSocket and JSON-RPC protocol experience

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).
