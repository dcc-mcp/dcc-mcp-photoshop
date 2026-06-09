# dcc-mcp-photoshop

[![PyPI](https://img.shields.io/pypi/v/dcc-mcp-photoshop)](https://pypi.org/project/dcc-mcp-photoshop/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-yellow)](https://github.com/dcc-mcp/dcc-mcp-photoshop)
[![Release](https://img.shields.io/github/v/release/dcc-mcp/dcc-mcp-photoshop)](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)

Adobe Photoshop adapter for the [DCC Model Context Protocol](https://github.com/dcc-mcp/dcc-mcp-core) ecosystem.
Bridges AI agents (Claude Desktop, Cursor, GitHub Copilot) to Adobe Photoshop via a UXP WebSocket plugin.

---

## Architecture

```
AI Agent (Claude Desktop / Cursor / Copilot)
    │  MCP Streamable HTTP (port 8765)
    ▼
PhotoshopMcpServer  [this package, Python]
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

## Features

**Current (v0.1.x):**
- ✅ UXP plugin (WebSocket client inside Photoshop) with exponential back-off reconnect
- ✅ `PhotoshopBridge` WebSocket server (Python, port 9001) with JSON-RPC 2.0 protocol
- ✅ 20+ Photoshop skills across 4 skill packages
- ✅ Skill authoring helpers (`ps_success`, `ps_error`, `with_photoshop`)
- ✅ `PhotoshopMcpServer` wrapping `dcc-mcp-core` (4-seam controller)
- ✅ Standalone binary (no Python runtime required)
- ✅ Cross-process RPC bridge support for gateway mode
- ✅ Lazy skill loading via `load_skill` meta-tool

**Planned:**
- [ ] Smart Object operations
- [ ] Selection tools (marquee, magic wand, lasso)
- [ ] Filter application (blur, sharpen, noise, etc.)
- [ ] Color adjustments (levels, curves, hue/saturation)
- [ ] Batch processing
- [ ] Photoshop 2025+ UXP API compatibility

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

## Installation

dcc-mcp-photoshop ships through **three distribution channels**. Choose the one that fits your environment.

### 1. PyPI (Python package)

```bash
pip install dcc-mcp-photoshop
```

Or via `uvx` (uv's pip interface):

```bash
uvx --with dcc-mcp-photoshop dcc-mcp-photoshop --embedded
```

From source:

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-photoshop.git
cd dcc-mcp-photoshop
pip install -e ".[dev]"
```

### 2. Standalone binary

Each [GitHub Release](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases) includes platform-specific binaries built with PyInstaller. No Python runtime required.

| Platform | Binary name | Architecture |
|----------|-------------|--------------|
| Windows | `dcc-mcp-photoshop-windows.exe` | x86_64 |
| Linux | `dcc-mcp-photoshop-linux` | x86_64 |
| macOS | `dcc-mcp-photoshop-macos` | x86_64 / arm64 |

```bash
# Download and run (example: Linux)
curl -L https://github.com/dcc-mcp/dcc-mcp-photoshop/releases/download/v0.1.6/dcc-mcp-photoshop-linux \
  -o dcc-mcp-photoshop
chmod +x dcc-mcp-photoshop
./dcc-mcp-photoshop --help
```

The binary includes built-in skills and all dependencies. It accepts the same flags as the Python entry point.

### 3. UXP .ccx plugin

Install the `.ccx` into Photoshop if you only need the UXP sidecar (bridge + MCP server):

1. Download the `.ccx` from the [latest release assets](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)
2. Open **Creative Cloud Desktop** → **Plugins** → **Manage Plugins**
3. Click the gear icon → **Install from file...**
4. Select the downloaded `.ccx` file
5. Restart Photoshop

Manual install (Windows):
```powershell
copy dcc-mcp-photoshop-bridge-0.1.6.ccx "$env:APPDATA\Adobe\UXP\Plugins\External\"
```

Manual install (macOS):
```bash
cp dcc-mcp-photoshop-bridge-0.1.6.ccx ~/Library/Application\ Support/Adobe/UXP/Plugins/External/
```

### Verify Installation

```bash
dcc-mcp-photoshop --version
```

## Configuration

### MCP Client Configuration

Add a `photoshop` server entry to your MCP client's configuration file.

#### Claude Desktop (`claude_desktop_config.json`)

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

For the **production gateway mode** (using `dcc-mcp-server.exe` externally):

```json
{
  "mcpServers": {
    "photoshop": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

See [Gateway Mode](#gateway-mode-recommended-for-deployment) below for the full setup.

#### Cursor

In Cursor Settings → Features → MCP Servers:

```
Name: photoshop
Type: command
Command: dcc-mcp-photoshop --embedded
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

## UXP Plugin Setup

The UXP plugin (`bridge/uxp-plugin/`) is the JavaScript component that runs inside Adobe Photoshop and provides the WebSocket bridge.

### How it works

```
┌───────────────────────────────────────────────────┐
│  Python Process                                    │
│  ┌─────────────────────────────────────────────┐   │
│  │  PhotoshopBridge (WS Server :9001)           │   │
│  └─────────────────────────────────────────────┘   │
│           ▲ connects to                            │
│           ║                                        │
├───────────────────────────────────────────────────┤
│  Adobe Photoshop                                   │
│  ┌─────────────────────────────────────────────┐   │
│  │  UXP Plugin (WS Client)                     │   │
│  │  - index.js: all handlers                    │   │
│  │  - manifest.json: plugin metadata            │   │
│  │  - index.html: panel UI                      │   │
│  └─────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┘
```

### Installing from source (development)

1. **Prepare the plugin directory**: The plugin lives at `bridge/uxp-plugin/` in this repository.
2. **Load in Photoshop**:
   - Open Photoshop
   - Go to **Plugins** → **Development** → **Load Plugin...**
   - Navigate to `bridge/uxp-plugin/` and select `manifest.json`
3. The plugin appears in the Plugins panel as "dcc-mcp Bridge". Click **Enable** — the WebSocket client automatically connects to `ws://localhost:9001`.

### Plugin features

- **Exponential back-off reconnect**: 3s → 6s → 12s → ... → 60s maximum
- **Persistent log file**: Written to UXP PluginData directory (`bridge.log`)
- **Panel UI**: Shows connection status (Connected / Disconnected / Connecting) and recent log entries
- **Manual connect/disconnect buttons** in the panel

### Plugin manifest

`bridge/uxp-plugin/manifest.json` declares:

| Field | Value |
|-------|-------|
| Plugin ID | `com.dcc-mcp.photoshop-bridge` |
| Name | `dcc-mcp Bridge` |
| Host app | Photoshop (PS) |
| Min version | Photoshop 2022 (22.0.0) |
| Network permissions | All domains |
| File system | Request access |

## Quick Start

### Embedded Mode (Development)

Start the MCP HTTP server and WebSocket bridge in one process:

```bash
python -m dcc_mcp_photoshop --embedded
```

Or via the installed CLI:

```bash
dcc-mcp-photoshop --embedded
```

Output:
```
dcc-mcp-photoshop v0.1.6

  [EMBEDDED MODE] MCP server + WebSocket bridge (dev only)
  MCP server  : http://localhost:8765/mcp
  WS bridge   : ws://localhost:9001
  RPC endpoint: http://localhost:9100/rpc

Waiting for Photoshop UXP plugin to connect...
Press Ctrl+C to stop.

[○] waiting for UXP plugin...
```

Once Photoshop is running with the UXP plugin, you will see:
```
[✓] CONNECTED — Untitled-1.psd
```

Your MCP client can now connect to `http://127.0.0.1:8765/mcp`.

### Bridge-Only Mode (Default)

Start only the WebSocket bridge (for use with `dcc-mcp-server.exe` externally):

```bash
dcc-mcp-photoshop
```

Output:
```
dcc-mcp-photoshop v0.1.6

  [BRIDGE-ONLY MODE] Requires dcc-mcp-server.exe running separately
  WS bridge   : ws://localhost:9001
  RPC endpoint: http://localhost:9100/rpc

MCP clients: http://127.0.0.1:8765/mcp (direct) or http://127.0.0.1:9765/mcp/dcc/photoshop (gateway)

Waiting for Photoshop UXP plugin to connect...
Press Ctrl+C to stop.
```

### Gateway Mode (Recommended for Deployment)

This mode uses the standalone `dcc-mcp-server.exe` for the MCP server and `dcc-mcp-photoshop` as a lightweight bridge plugin.

**Terminal 1** — Start the MCP server (Rust binary, no Python needed):
```bash
dcc-mcp-server.exe --dcc photoshop --mcp-port 8765 \
  --skill-paths ./skills --no-bridge \
  --gateway-port 9765 --registry-dir ~/.dcc-mcp/registry
```

**Terminal 2** — Start the bridge plugin (Python, connects to UXP):
```bash
python -m dcc_mcp_photoshop
```

**MCP clients** connect to:
- `http://127.0.0.1:8765/mcp` — Direct, stable port
- `http://127.0.0.1:9765/mcp/dcc/photoshop` — Gateway proxy (auto-detects DCC type)

### Python API

```python
import dcc_mcp_photoshop

handle = dcc_mcp_photoshop.start_server(
    port=8765,
    ws_port=9001,
)

print(f"MCP URL: {handle.mcp_url()}")

# ... use with Claude Desktop, Cursor, etc.

handle.shutdown()
```

### CLI Reference

```
dcc-mcp-photoshop [OPTIONS]

Options:
  --embedded          Embedded mode: MCP server + bridge in one process (dev only)
  --mcp-port PORT     MCP HTTP server port (embedded mode; default: 8765)
  --ws-port PORT      WebSocket bridge port for UXP plugin (default: 9001)
  --ws-host HOST      WebSocket bind host (default: localhost)
  --rpc-port PORT     HTTP RPC server port for cross-process bridge access (default: 9100)
  --gateway-port PORT Gateway competition port (embedded mode; default: env or 9765)
  --server-name NAME  Server name reported in MCP initialize (default: photoshop-mcp)
  --skill-paths PATH  Extra skill directories
  --no-builtins       Do not discover built-in skills
  --verbose, -v       Enable debug logging
  --version           Show version and exit
```

## Built-in Skills

dcc-mcp-photoshop ships with **4 skill packages** containing **20+ tools** organized by domain.
Skills are **lazy-loaded**: only meta-tools are available initially; use the MCP `load_skill` tool
to load the skill package you need.

### photoshop-document

Document information and layer listing.

| Tool | Description | Read-only | Inputs |
|------|-------------|-----------|--------|
| `get_document_info` | Get metadata about the active Photoshop document (name, size, resolution, color mode) | ✅ | _(none)_ |
| `list_layers` | List all layers in the active document. Set `include_hidden=false` to exclude hidden layers | ✅ | `include_hidden` (bool, default: true) |

### photoshop-image

Document creation, export, canvas/image resize, flatten, and merge operations.

| Tool | Description | Read-only | Inputs |
|------|-------------|-----------|--------|
| `create_document` | Create a new document with specified dimensions, resolution and color mode | ❌ | `name`, `width` (1920), `height` (1080), `resolution` (72), `color_mode` (rgb/cmyk/grayscale/lab), `bit_depth` (8/16/32), `fill` (white/black/transparent/background) |
| `export_document` | Export the active document to PNG, JPG, TIFF, or PSD | ❌ | `path` (required), `format` (png/jpg/tiff/psd), `quality` (0-100, default 90) |
| `save_document` | Save the active document in its current format | ❌ | _(none)_ |
| `resize_canvas` | Resize canvas without scaling content | ❌ | `width` (required), `height` (required), `anchor` (center/top_left/etc.) |
| `resize_image` | Scale the image (resamples content) | ❌ | `width` (required), `height` (required), `resample` (bicubic/bilinear/etc.), `constrain_proportions` |
| `flatten_image` | Flatten all layers into a single background layer | ❌ *(destructive)* | _(none)_ |
| `merge_visible_layers` | Merge all visible layers | ❌ *(destructive)* | _(none)_ |

### photoshop-layers

Full CRUD for layers plus visual property changes.

| Tool | Description | Read-only | Inputs |
|------|-------------|-----------|--------|
| `create_layer` | Create a pixel, group, or adjustment layer | ❌ | `name` (default: "Layer"), `layer_type` (pixel/group/adjustment) |
| `delete_layer` | Delete a named layer | ❌ *(destructive)* | `name` (required) |
| `duplicate_layer` | Duplicate a named layer | ❌ | `name` (required), `new_name` (optional) |
| `rename_layer` | Rename a layer | ❌ | `name` (required), `new_name` (required) |
| `set_layer_opacity` | Set opacity (0-100) of a named layer | ❌ | `name` (required), `opacity` (0-100, required) |
| `set_layer_visibility` | Show or hide a named layer | ❌ | `name` (required), `visible` (bool, required) |
| `set_layer_blend_mode` | Set blend mode (normal, multiply, screen, overlay, etc.) | ❌ | `name` (required), `blend_mode` (required, 27 modes) |
| `fill_layer` | Fill a layer with solid color (hex) or transparent | ❌ | `name` (required), `color` (hex, default: #ffffff), `opacity` (0-100) |

### photoshop-text

Text layer creation, editing, and inspection.

| Tool | Description | Read-only | Inputs |
|------|-------------|-----------|--------|
| `create_text_layer` | Create a new text layer with content and styling | ❌ | `content` (required), `name`, `x` (100), `y` (100), `font` (ArialMT), `size` (48), `color` (#000000), `alignment` (left/center/right), `bold`, `italic` |
| `update_text_layer` | Update text content or style of an existing text layer | ❌ | `name` (required), `content`, `font`, `size`, `color`, `alignment`, `bold`, `italic` |
| `get_text_layer_info` | Get text content and style properties of a text layer | ✅ | `name` (required) |

## Skill Authoring

There are two approaches to authoring Photoshop skills:

### New-style (adobepy facade, recommended)

Use the `adobepy` facade layer and `adobe.dcc_mcp` result helpers:

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

Directly use the WebSocket bridge for backward compatibility:

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

### SKILL.md format

Each skill package requires a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: photoshop-document
description: "Adobe Photoshop document management — query documents and layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, document, layers, adobe]
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: get_document_info
    description: "Get metadata about the active Photoshop document"
    source_file: scripts/get_document_info.py
    read_only: true
    destructive: false
    idempotent: true
  - name: list_layers
    description: "List all layers in the active document"
    source_file: scripts/list_layers.py
    read_only: true
    destructive: false
    idempotent: true
---
```

### tools.yaml format

Tools can alternatively be declared in a `tools.yaml` file next to the `SKILL.md`:

```yaml
tools:
  - name: my_tool
    description: "Description of what this tool does"
    source_file: scripts/my_tool.py
    inputSchema:
      type: object
      properties:
        param1:
          type: string
          description: Parameter description
    read_only: false
    destructive: false
    idempotent: true
```

### Setting custom skill paths

```bash
# Environment variable (colon-separated on macOS/Linux, semicolon on Windows)
export DCC_MCP_PHOTOSHOP_SKILL_PATHS=/path/to/my/skills

# Or via CLI flag
dcc-mcp-photoshop --embedded --skill-paths /path/to/my/skills
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
│       ├── create_document.py
│       ├── export_document.py
│       ├── save_document.py
│       ├── resize_canvas.py
│       ├── resize_image.py
│       ├── flatten_image.py
│       └── merge_visible_layers.py
├── photoshop-layers/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
│       ├── create_layer.py
│       ├── delete_layer.py
│       ├── duplicate_layer.py
│       ├── rename_layer.py
│       ├── set_layer_opacity.py
│       ├── set_layer_visibility.py
│       ├── set_layer_blend_mode.py
│       └── fill_layer.py
├── photoshop-text/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
│       ├── create_text_layer.py
│       ├── update_text_layer.py
│       └── get_text_layer_info.py
```

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

### RPC Request (Python → UXP)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "ps.listLayers",
  "params": {"include_hidden": true}
}
```

### RPC Response (UXP → Python)

Success:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [
    {"name": "Background", "type": "pixel", "visible": true, "opacity": 100},
    {"name": "Layer 1", "type": "pixel", "visible": true, "opacity": 100}
  ]
}
```

Error:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "No active document",
    "hint": "Open a document first"
  }
}
```

### Progress Notifications (UXP → Python)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "type": "progress",
  "progress": {"current": 50, "total": 100, "message": "Exporting..."}
}
```

### Disconnect

```json
{
  "type": "disconnected",
  "reason": "Server stopped"
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

Ensure these ports are not blocked by a firewall.

### Skill not found

If an expected tool is not available:
1. Use the MCP `load_skill` meta-tool to load the skill package
2. Or restart the server with `--no-builtins` omitted (default loads built-in skills)

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
- ✅ Package structure and API design
- ✅ PhotoshopBridge WebSocket client scaffold
- ✅ Skill authoring helpers
- ✅ UXP plugin architecture design

### v0.2.0 — UXP Plugin + Bridge ✅
- ✅ UXP plugin WebSocket client (JavaScript)
- ✅ Python bridge WebSocket server
- ✅ JSON-RPC 2.0 protocol implementation
- ✅ Release distribution (pip, binary, .ccx)
- ✅ 20+ Photoshop skills
- ✅ Cross-process RPC bridge

### v0.3.0 — Skills & Polish (next)
- [ ] Smart Object support
- [ ] Selection tools (marquee, magic wand)
- [ ] Filter application (blur, sharpen, etc.)
- [ ] Color adjustments (levels, curves, hue/saturation)
- [ ] Batch processing

### v1.0.0 — Production Ready
- [ ] Photoshop 2025+ UXP API compatibility
- [ ] Performance optimizations
- [ ] Authentication and security hardening

## Contributing

This project is especially looking for contributors with:
- Adobe UXP / ExtendScript experience
- Photoshop automation knowledge
- WebSocket and JSON-RPC protocol experience

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).
