# Photoshop UXP WebSocket Bridge Protocol v0

**Version**: 0.1.0
**Transport**: WebSocket (Python server, UXP client)
**Message format**: JSON-RPC 2.0 superset
**Default endpoint**: `ws://localhost:9001`

---

## 1. Architecture

```
MCP Client ──HTTP──► Gateway (dcc-mcp-core) ──call()──► PhotoshopBridge (Python)
                                                               │
                                           WebSocket server localhost:9001
                                                               │
                                           Photoshop UXP plugin (WS client)
                                                               │
                                           Photoshop UXP API
```

Python starts a WebSocket server. The UXP plugin connects as a client (UXP does not support WebSocket server mode). Python sends JSON-RPC 2.0 requests; UXP executes them against the Photoshop API and returns responses.

---

## 2. Connection Lifecycle

### 2.1 State Machine

```
 ┌──────────┐  server starts   ┌──────────────┐  UXP connects    ┌───────────────┐
 │  CLOSED  │ ───────────────► │  LISTENING   │ ────────────────► │   CONNECTED   │
 └──────────┘                  └──────────────┘                   └───────────────┘
       ▲                              │                                  │    │
       │                              │ UXP fails to connect             │    │
       │ server.stop()                ▼                                  │    │ UXP disconnects
       │                     ┌──────────────┐                            │    ▼
       └─────────────────────│    ERROR     │◄───────────────────────────┘
                             └──────────────┘                    ┌──────────────┐
                                                                 │ DISCONNECTED │
                                                                 └──────────────┘
                                                                        │
                                                                        │ auto-reconnect (3s)
                                                                        ▼
                                                                 ┌───────────────┐
                                                                 │ RECONNECTING  │──► CONNECTED
                                                                 └───────────────┘
```

### 2.2 Lifecycle Events

| Event | Direction | Trigger | Payload |
|-------|-----------|---------|---------|
| `hello` | UXP → Python | WebSocket onopen | `{type, protocol, version, client}` |
| `hello_ack` | Python → UXP | After hello received | `{type, protocol, version}` |
| `disconnected` | Python → UXP | UXP disconnects or server stops | `{type: "disconnected", reason}` |
| `reconnecting` | UXP → Python | On reconnect attempt | `{type: "hello", reconnect: true, ...}` |
| `progress` | UXP → Python | Long-running operation progress | `{jsonrpc, id, type: "progress", progress}` |
| `connected` | UXP → Python | First hello after connection | `{type: "hello", ...}` |

### 2.3 Hello Handshake

**UXP → Python** (on WebSocket open):
```json
{
    "type": "hello",
    "protocol": "photoshop-bridge",
    "version": "0.1.0",
    "client": "photoshop-uxp",
    "reconnect": false
}
```

**Python → UXP** (after receiving hello):
```json
{
    "type": "hello_ack",
    "protocol": "photoshop-bridge",
    "version": "0.1.0"
}
```

### 2.4 Disconnection

When the UXP client disconnects:
- Python fails all pending RPC calls with `BridgeConnectionError("UXP plugin disconnected")`
- Python sets `_connected = false`
- UXP auto-reconnects after 3 seconds (unless `_stopped = true`)

When Python shuts down the server:
- Python closes the WebSocket connection
- UXP `onclose` fires; UXP enters reconnecting state

---

## 3. RPC Envelope

### 3.1 Request (Python → UXP)

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "ps.getDocumentInfo",
    "params": {}
}
```

### 3.2 Success Response (UXP → Python)

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {}
}
```

### 3.3 Error Response (UXP → Python)

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32601,
        "message": "Method not found: ps.unknownMethod",
        "hint": "Use ps.describeApi to list available methods",
        "data": {
            "method": "ps.unknownMethod"
        }
    }
}
```

### 3.4 Progress Notification (UXP → Python)

```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "type": "progress",
    "progress": {
        "current": 50,
        "total": 100,
        "message": "Exporting document to /tmp/export.png...",
        "stage": "export"
    }
}
```

---

## 4. Error Codes

### 4.1 Standard JSON-RPC 2.0 Codes

| Code | Name | Description |
|------|------|-------------|
| `-32700` | Parse error | Invalid JSON received |
| `-32600` | Invalid Request | Not a valid JSON-RPC request |
| `-32601` | Method not found | Method does not exist |
| `-32602` | Invalid params | Missing or invalid parameters |
| `-32603` | Internal error | Unexpected handler error |

### 4.2 Photoshop Bridge Custom Codes

| Code | Name | Description |
|------|------|-------------|
| `-32001` | No Active Document | No document open in Photoshop |
| `-32002` | Layer Not Found | Named layer does not exist |
| `-32003` | Unsupported Format | Export format not supported |
| `-32004` | File Not Found | Path does not exist on disk |
| `-32005` | Script Error | UXP script execution failed |
| `-32006` | Timeout | Operation exceeded timeout |
| `-32007` | Disconnected | UXP connection lost mid-operation |

---

## 5. Method Namespace

### 5.1 Document Operations

| Method | Parameters | Returns |
|--------|------------|---------|
| `ps.getDocumentInfo` | _(none)_ | Document metadata object |
| `ps.listDocuments` | _(none)_ | Array of document metadata |
| `ps.createDocument` | `name?`, `width?`, `height?`, `resolution?`, `color_mode?`, `bit_depth?` | Created document metadata |
| `ps.openDocument` | `path` (required) | Opened document metadata |
| `ps.saveDocument` | _(none)_ | `{saved, path}` |
| `ps.closeDocument` | `save?` (boolean, default false) | `{closed}` |
| `ps.exportDocument` | `path` (required), `format?` (png/jpg/tiff/psd), `quality?` (jpg, 0-100) | `{exported, path, format}` |

### 5.2 Layer Operations

| Method | Parameters | Returns |
|--------|------------|---------|
| `ps.listLayers` | `include_hidden?` (boolean, default true) | Layer tree array |
| `ps.createLayer` | `name?`, `type?` (pixel/group) | `{id, name, type}` |
| `ps.deleteLayer` | `name` (required) | `{deleted, name}` |
| `ps.setLayerVisibility` | `name`, `visible` (both required) | `{name, visible}` |
| `ps.renameLayer` | `name`, `new_name` (both required) | `{old_name, name}` |
| `ps.setLayerOpacity` | `name`, `opacity` (both required, 0-100) | `{name, opacity}` |
| `ps.duplicateLayer` | `name` (required), `new_name?` | `{id, name}` |
| `ps.setLayerBlendMode` | `name`, `blend_mode` (both required) | `{name, blend_mode}` |
| `ps.fillLayer` | `name`, `color` (both required) | `{filled, name, color}` |

### 5.3 Image Operations

| Method | Parameters | Returns |
|--------|------------|---------|
| `ps.resizeCanvas` | `width`, `height` (both required) | `{width, height}` |
| `ps.resizeImage` | `width`, `height` (both required) | `{width, height}` |
| `ps.flattenImage` | _(none)_ | `{flattened}` |
| `ps.mergeVisibleLayers` | _(none)_ | `{merged, layer_name}` |

### 5.4 Text Operations

| Method | Parameters | Returns |
|--------|------------|---------|
| `ps.createTextLayer` | `content` (required), `name?` | `{id, name, content}` |
| `ps.updateTextLayer` | `name`, `content` (both required) | `{name, content}` |
| `ps.getTextLayerInfo` | `name` (required) | `{name, content, font, size, color, alignment, bold, italic}` |

### 5.5 Script / Meta Operations

| Method | Parameters | Returns |
|--------|------------|---------|
| `ps.executeScript` | `code` (required) | Script return value |
| `ps.executeAction` | `action`, `action_set` (both required) | `{executed, action, action_set}` |
| `ps.describeApi` | _(none)_ | `{protocol, version, methods: [...]}` |
| `ps.invoke` | `path`, `args?`, `kwargs?`, `modal?` | Reflected API result |
| `ps.batchPlay` | `commands`, `options?`, `modal?` | batchPlay result |

---

## 6. Protocol Version Compatibility

| Version | Changes |
|---------|---------|
| `0.1.0` | Initial protocol: JSON-RPC 2.0 + hello handshake + progress notifications + extended error envelope |

Version negotiation: The UXP plugin declares its protocol version in the `hello` message. If the Python server requires a different version, it responds with `hello_ack` containing `compatible: false` and an `error` field explaining the mismatch.

---

## 7. Contract Tests

See `tests/test_protocol.py` and `tests/conftest.py` (mock UXP peer).
