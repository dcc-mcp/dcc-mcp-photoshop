# dcc-mcp UXP Plugin for Photoshop

This directory contains the Adobe UXP plugin that runs inside Photoshop and
exposes a WebSocket server for the Python bridge to connect to.

The UXP plugin is bundled as a `.ccx` archive for distribution. See
[`docs/distribution.md`](../../docs/distribution.md) for install instructions.

## Architecture

```
Photoshop (UXP Plugin, JavaScript)
    +-- Starts WebSocket server on localhost:3000
    +-- Receives JSON-RPC 2.0 messages from Python bridge
    +-- Executes Photoshop UXP API calls
    +-- Returns results as JSON

Python Bridge (dcc-mcp-photoshop)
    +-- Connects to WebSocket server
    +-- Translates MCP tool calls to JSON-RPC
    +-- Returns results to dcc-mcp-core
```

## Protocol

### Request format (Python -> Photoshop)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "ps.listLayers",
  "params": {
    "include_hidden": true
  }
}
```

### Response format (Photoshop -> Python)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [
    {"name": "Background", "type": "pixel", "visible": true},
    {"name": "Layer 1", "type": "pixel", "visible": true}
  ]
}
```

### Error response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "No active document"
  }
}
```

## Supported Methods (Planned)

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `ps.executeScript` | `code: str` | `any` | Execute a JavaScript/UXP code snippet |
| `ps.getDocumentInfo` | — | `dict` | Get active document metadata |
| `ps.listDocuments` | — | `list` | List all open documents |
| `ps.listLayers` | `include_hidden: bool` | `list` | List layers in active document |
| `ps.createLayer` | `name: str, type: str` | `dict` | Create a new layer |
| `ps.deleteLayer` | `name: str` | `bool` | Delete a layer by name |
| `ps.applyFilter` | `layer: str, filter: str, params: dict` | `dict` | Apply a filter to a layer |
| `ps.exportDocument` | `path: str, format: str` | `dict` | Export the document |
| `ps.setLayerVisibility` | `name: str, visible: bool` | `bool` | Show/hide a layer |
| `ps.getSelection` | — | `dict` | Get current selection bounds |

## Installation (Planned)

### Requirements
- Adobe Photoshop 2022 or later (UXP API support)
- Creative Cloud Desktop App

### Steps
1. Open Photoshop
2. Go to **Plugins > Development > Load Plugin...**
3. Navigate to this directory and select `manifest.json`
4. The plugin will appear in the Plugins panel
5. Click **Enable** — the WebSocket server starts automatically on port 3000

### Verify Connection
```python
import websockets
import asyncio
import json

async def test():
    async with websockets.connect("ws://localhost:3000") as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ps.getDocumentInfo",
            "params": {}
        }))
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test())
```

## File Structure (Planned)

```
uxp-plugin/
├── manifest.json          # UXP plugin manifest
├── index.html             # Plugin panel UI (optional)
├── index.js               # Main plugin entry point
├── src/
│   ├── websocket-server.js  # WebSocket server implementation
│   ├── handlers/
│   │   ├── document.js      # Document-related handlers
│   │   ├── layers.js        # Layer-related handlers
│   │   ├── filters.js       # Filter handlers
│   │   └── export.js        # Export handlers
│   └── utils/
│       ├── jsonrpc.js       # JSON-RPC helpers
│       └── ps-helpers.js    # Photoshop UXP API wrappers
└── README.md
```

## Development Notes

### UXP API References
- [Adobe UXP API Documentation](https://developer.adobe.com/photoshop/uxp/)
- [Photoshop UXP Plugin Guide](https://developer.adobe.com/photoshop/uxp/2022/guides/)
- [UXP WebSocket API](https://developer.adobe.com/photoshop/uxp/2022/uxp-api/reference-js/Modules/network/WebSocket/)

### Key UXP APIs Used
- `require('photoshop').app` — Main Photoshop application object
- `require('photoshop').app.activeDocument` — Active document
- `require('photoshop').action.batchPlay` — Execute Action Manager operations
- `require('uxp').network.WebSocket` — WebSocket server (UXP-specific)
