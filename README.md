# dcc-mcp-photoshop

> Adobe Photoshop adapter for the [DCC Model Context Protocol](https://github.com/loonghao/dcc-mcp-core) ecosystem.
> Bridges AI agents to Photoshop via a UXP WebSocket plugin.

[![PyPI version](https://img.shields.io/pypi/v/dcc-mcp-photoshop.svg)](https://pypi.org/project/dcc-mcp-photoshop/)
[![Python](https://img.shields.io/pypi/pyversions/dcc-mcp-photoshop.svg)](https://pypi.org/project/dcc-mcp-photoshop/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Pre-Alpha](https://img.shields.io/badge/Status-Pre--Alpha-red.svg)]()

---

## Overview

`dcc-mcp-photoshop` connects AI agents (Claude, GPT-4, Cursor…) to **Adobe Photoshop** through the [Model Context Protocol](https://modelcontextprotocol.io/).

Unlike Maya or Blender, Photoshop does **not** have an embedded Python interpreter. This package uses a **WebSocket bridge architecture**:

```
AI Agent (Claude, Cursor, etc.)
    |
    | MCP Streamable HTTP
    v
PhotoshopMcpServer (Python, port 8765)
    |
    | JSON-RPC 2.0 over WebSocket
    v
Photoshop UXP Plugin (JavaScript, port 3000)
    |
    | Photoshop UXP API
    v
Adobe Photoshop
```

---

## Features

- **MCP Streamable HTTP server** (2025-03-26 spec) via dcc-mcp-core
- **WebSocket bridge** to Photoshop UXP plugin (JSON-RPC 2.0)
- **Skill-based architecture** — add capabilities by dropping skill directories
- **Graceful degradation** — server starts even when Photoshop is not running
- **Type-safe results** — all skills return `ActionResultModel`-compatible dicts
- **Decorator-based error handling** via `@with_photoshop`

### Planned Skills

| Skill | Description |
|-------|-------------|
| `photoshop-document` | Open, save, create, export documents |
| `photoshop-layers` | Create, delete, reorder, merge layers |
| `photoshop-selection` | Make selections, transform, fill |
| `photoshop-filters` | Apply blur, sharpen, smart filters |
| `photoshop-color` | Color adjustments, curves, levels |
| `photoshop-text` | Add and edit text layers |
| `photoshop-history` | Undo, redo, history states |

---

## Requirements

- **Adobe Photoshop 2022** or later (UXP API support required)
- **Python 3.8+**
- `dcc-mcp-core >= 0.12.14`
- `websockets >= 12.0`

---

## Installation

```bash
pip install dcc-mcp-photoshop
```

### Install the UXP Plugin

The Python bridge requires the companion UXP plugin running inside Photoshop:

1. Open **Photoshop**
2. Go to **Plugins > Development > Load Plugin...**
3. Navigate to `bridge/uxp-plugin/` and select `manifest.json`
4. Click **Enable** — the WebSocket server starts on `localhost:3000`

> See [bridge/uxp-plugin/README.md](bridge/uxp-plugin/README.md) for full details.

---

## Quick Start

### Step 1: Install and enable the UXP plugin in Photoshop

### Step 2: Start the Python bridge

```python
import dcc_mcp_photoshop

# Start MCP server (connects to Photoshop's UXP WebSocket on port 3000)
handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=3000)
print(handle.mcp_url())  # http://127.0.0.1:8765/mcp

# Photoshop is now available as an MCP tool provider
# Connect any MCP-compatible client (Claude Desktop, Cursor, etc.)

# Stop when done
handle.shutdown()
```

### Step 3: Connect your AI agent

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "photoshop": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

---

## Skill Authoring Guide

Skills are Python scripts in `skills/<skill-name>/scripts/`. Each script:
1. Uses `@with_photoshop` for automatic error handling, OR
2. Calls `get_bridge()` to communicate with Photoshop via JSON-RPC

### Example: List Layers

```python
# skills/photoshop-layers/scripts/list_layers.py
from dcc_mcp_photoshop.api import get_bridge, ps_success, with_photoshop


@with_photoshop
def list_layers(include_hidden: bool = True, **kwargs) -> dict:
    bridge = get_bridge()
    layers = bridge.call("ps.listLayers", include_hidden=include_hidden)
    return ps_success(
        f"Found {len(layers)} layer(s)",
        count=len(layers),
        layers=[l["name"] for l in layers],
    )


def main(**kwargs) -> dict:
    return list_layers(**kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
```

### Example: SKILL.md frontmatter

```yaml
---
name: photoshop-layers
description: "Photoshop layer management — create, delete, reorder, merge layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, layers, compositing]
license: "MIT"
depends: []
---
```

### Key helpers

| Helper | Description |
|--------|-------------|
| `ps_success(message, **ctx)` | Build success result dict |
| `ps_error(message, error, ...)` | Build failure result dict |
| `ps_from_exception(exc, ...)` | Build failure from exception |
| `get_bridge()` | Get the active PhotoshopBridge instance |
| `@with_photoshop` | Decorator for automatic error handling |
| `is_photoshop_available()` | Check if bridge is connected |

### Bridge API

```python
from dcc_mcp_photoshop.api import get_bridge

bridge = get_bridge()

# Execute any supported UXP method
info = bridge.call("ps.getDocumentInfo")
layers = bridge.call("ps.listLayers", include_hidden=True)
bridge.call("ps.createLayer", name="New Layer", type="pixel")
```

---

## Architecture Details

### DccCapabilities

This adapter declares:

```python
from dcc_mcp_core import DccCapabilities

caps = DccCapabilities(
    has_embedded_python=False,   # Photoshop has no Python runtime
    bridge_kind="websocket",     # Uses WebSocket bridge
    bridge_endpoint="ws://localhost:3000",
    file_operations=True,
    snapshot=True,
    scene_info=True,
)
```

### Bridge Protocol

The UXP plugin implements a JSON-RPC 2.0 server over WebSocket.
All `bridge.call(method, **params)` calls are serialized as:

```json
{"jsonrpc": "2.0", "id": 1, "method": "ps.listLayers", "params": {"include_hidden": true}}
```

---

## Roadmap

### v0.1.0 (Current — Placeholder)
- [x] Project scaffold matching dcc-mcp-maya structure
- [x] PhotoshopBridge placeholder (WebSocket client stub)
- [x] PhotoshopMcpServer (bridge mode, wraps dcc-mcp-core)
- [x] UXP plugin scaffold with JSON-RPC dispatcher stub
- [x] DccCapabilities declared with `bridge_kind="websocket"`

### v0.2.0 — WebSocket Implementation
- [ ] UXP plugin: real WebSocket server
- [ ] Python bridge: real websockets connection + async event loop
- [ ] `ps.getDocumentInfo`, `ps.listDocuments`, `ps.listLayers`
- [ ] `photoshop-document` skill: get_document_info, list_layers

### v0.3.0 — Core Skills
- [ ] `photoshop-layers` skill: create, delete, reorder, merge
- [ ] `photoshop-selection` skill: marquee, lasso, magic wand
- [ ] `photoshop-color` skill: curves, levels, hue/saturation

### v0.4.0 — Advanced Features
- [ ] `photoshop-filters` skill: blur, sharpen, smart filters
- [ ] `photoshop-text` skill: add, edit, style text layers
- [ ] `photoshop-history` skill: undo/redo, history states
- [ ] Batch operations support

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Key areas:
- UXP plugin implementation (`bridge/uxp-plugin/`)
- WebSocket bridge implementation (`src/dcc_mcp_photoshop/bridge.py`)
- New skill scripts (`src/dcc_mcp_photoshop/skills/`)

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Related Projects

- [dcc-mcp-core](https://github.com/loonghao/dcc-mcp-core) — Core framework
- [dcc-mcp-maya](https://github.com/loonghao/dcc-mcp-maya) — Maya adapter
- [dcc-mcp-unreal](https://github.com/loonghao/dcc-mcp-unreal) — Unreal Engine adapter
- [dcc-mcp-zbrush](https://github.com/loonghao/dcc-mcp-zbrush) — ZBrush adapter
