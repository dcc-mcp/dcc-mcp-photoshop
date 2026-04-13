# dcc-mcp-photoshop

[![PyPI](https://img.shields.io/pypi/v/dcc-mcp-photoshop)](https://pypi.org/project/dcc-mcp-photoshop/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Pre-Alpha](https://img.shields.io/badge/status-pre--alpha-orange)](https://github.com/loonghao/dcc-mcp-photoshop)

Adobe Photoshop adapter for the [DCC Model Context Protocol](https://github.com/loonghao/dcc-mcp-core) ecosystem.
Bridges AI agents (Claude, Cursor, Copilot) to Adobe Photoshop via UXP WebSocket.

> ⚠️ **Pre-Alpha**: UXP plugin implementation is pending. API design is stable.

## Architecture

```
AI Agent (Claude / Cursor)
    ↓  MCP Streamable HTTP (port 8765)
PhotoshopMcpServer  [this package, Python]
    ↓  WebSocket JSON-RPC (port 3000)
UXP Plugin  [bridge/uxp-plugin/, JavaScript]
    ↓  Photoshop UXP API
Adobe Photoshop 2022+
```

**DCC Capabilities:**
```python
DccCapabilities(
    has_embedded_python=False,
    bridge_kind="websocket",
    bridge_endpoint="ws://localhost:3000",
    snapshot=True,
    file_operations=True,
    selection=True,
)
```

## Features

**Current (v0.1.0 — Placeholder):**
- ✅ Package structure and API design
- ✅ `PhotoshopBridge` WebSocket client scaffold
- ✅ Skill authoring helpers (`ps_success`, `ps_error`, `with_photoshop`)
- ✅ `PhotoshopMcpServer` wrapping `dcc-mcp-core`
- ⏳ UXP plugin implementation (pending)
- ⏳ WebSocket bridge implementation (pending)

**Planned:**
- Document management (open, save, export)
- Layer management (create, delete, reorder, blend modes)
- Selection tools (marquee, lasso, magic wand)
- Filter application
- Color adjustments
- Smart Object operations
- Batch processing

## Requirements

- Adobe Photoshop 2022+ (UXP support)
- Python 3.8+
- `dcc-mcp-core >= 0.12.14`
- `websockets >= 12.0`

## Installation

```bash
pip install dcc-mcp-photoshop
```

Or from source:

```bash
git clone https://github.com/loonghao/dcc-mcp-photoshop
cd dcc-mcp-photoshop
pip install -e ".[dev]"
```

## Photoshop UXP Plugin Setup

1. Install the UXP plugin from `bridge/uxp-plugin/` (pending implementation)
2. Open Photoshop
3. Go to **Plugins > Browse Plugins**
4. Install from local manifest
5. The plugin starts a WebSocket server on port 3000 automatically

## Quick Start

```python
import dcc_mcp_photoshop

handle = dcc_mcp_photoshop.start_server(
    port=8765,     # MCP HTTP port
    ws_port=3000,  # Photoshop UXP WebSocket port
)
print(handle.mcp_url())
handle.shutdown()
```

## Skill Authoring Guide

Photoshop skills use `get_bridge()` to communicate via the UXP WebSocket plugin
instead of importing a DCC Python module directly.

```python
from dcc_mcp_core.skill import skill_entry
from dcc_mcp_photoshop.api import get_bridge, with_photoshop, ps_success


@skill_entry
@with_photoshop
def list_layers(document_index: int = 0, **kwargs) -> dict:
    """List all layers in a Photoshop document."""
    bridge = get_bridge()
    layers = bridge.call("ps.listLayers", documentIndex=document_index)
    return ps_success(
        f"Found {len(layers)} layer(s)",
        count=len(layers),
        layers=[layer["name"] for layer in layers],
    )


def main(**kwargs):
    return list_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
```

### SKILL.md format

```yaml
---
name: my-photoshop-skill
description: "Description of what this skill does"
dcc: photoshop
version: "1.0.0"
tags: [photoshop, layers, document]
license: "MIT"
depends: []
---
```

### Setting skill paths

```bash
export DCC_MCP_PHOTOSHOP_SKILL_PATHS=/path/to/my/skills
```

## UXP Plugin Protocol

The UXP plugin (JavaScript) runs inside Photoshop and implements a WebSocket
server with JSON-RPC 2.0 protocol:

**Request format:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "ps.listLayers",
  "params": {"documentIndex": 0}
}
```

**Response format:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [{"name": "Background", "visible": true}]
}
```

**Supported methods (planned):**

| Method | Description |
|--------|-------------|
| `ps.executeScript` | Execute JavaScript/UXP code |
| `ps.getDocumentInfo` | Get active document metadata |
| `ps.listDocuments` | List all open documents |
| `ps.listLayers` | List layers in active document |
| `ps.createLayer` | Create a new layer |
| `ps.applyFilter` | Apply a filter to a layer |
| `ps.exportDocument` | Export document to file |

## Roadmap

### v0.1.0 — Foundation (current)
- [x] Package structure and API design
- [x] PhotoshopBridge WebSocket client scaffold
- [x] Skill authoring helpers
- [ ] UXP plugin architecture design

### v0.2.0 — UXP Plugin + Bridge
- [ ] UXP plugin WebSocket server (JavaScript)
- [ ] Python bridge WebSocket client
- [ ] JSON-RPC 2.0 protocol implementation
- [ ] Authentication and security

### v0.3.0 — Document Skills
- [ ] get_document_info skill
- [ ] list_documents skill
- [ ] list_layers skill
- [ ] create_layer skill
- [ ] export_document skill

### v0.4.0 — Advanced Skills
- [ ] apply_filter skill
- [ ] color_adjustment skill
- [ ] selection_tool skill
- [ ] smart_object skill

### v1.0.0 — Production Ready
- [ ] Smart Object support
- [ ] Batch processing
- [ ] Photoshop 2025+ UXP API compatibility
- [ ] Performance optimizations

## Contributing

This project is especially looking for contributors with:
- Adobe UXP / ExtendScript experience
- Photoshop automation knowledge
- WebSocket and JSON-RPC protocol experience

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).
