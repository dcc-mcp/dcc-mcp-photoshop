# Product Requirements Document: dcc-mcp-photoshop

**Version**: 0.1.0 (Placeholder)
**Status**: Pre-Alpha
**Target**: Adobe Photoshop 2022+

---

## 1. Problem Statement

AI agents (Claude, GPT-4, Cursor…) cannot interact with Adobe Photoshop because:

1. Photoshop does **not** expose a Python interpreter (unlike Maya, Blender, Unreal)
2. There is no standard API for external processes to control Photoshop programmatically
3. Existing solutions (ExtendScript/CEP) are deprecated; the new UXP API requires JavaScript

This package solves this by introducing a **WebSocket bridge** between the Python MCP server and a JavaScript UXP plugin running inside Photoshop.

---

## 2. Goals

### Must Have (v0.2.0)
- [ ] UXP plugin with WebSocket server on configurable port (default 3000)
- [ ] Python bridge connecting to UXP WebSocket (JSON-RPC 2.0)
- [ ] MCP HTTP server wrapping dcc-mcp-core
- [ ] Basic skills: document info, layer listing, document export
- [ ] Graceful fallback when Photoshop is not running

### Should Have (v0.3.0)
- [ ] Layer CRUD (create, rename, delete, reorder, merge)
- [ ] Selection tools (marquee, lasso, select by color)
- [ ] Color adjustments (curves, levels, hue/saturation, brightness/contrast)
- [ ] Text layer creation and editing

### Nice to Have (v0.4.0+)
- [ ] Smart filter application
- [ ] Action recording and playback
- [ ] Batch document processing
- [ ] History/undo/redo management
- [ ] Generator (smart object) support

---

## 3. Non-Goals

- Real-time collaboration (multiplayer editing)
- Photoshop Elements support (different UXP surface area)
- Older Photoshop CS versions (pre-UXP)
- Direct pixel manipulation (performance concerns)

---

## 4. Architecture

### 4.1 Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent (Client)                        │
│              Claude Desktop / Cursor / OpenClaw              │
└───────────────────────────┬─────────────────────────────────┘
                            │ MCP Streamable HTTP (port 8765)
┌───────────────────────────▼─────────────────────────────────┐
│              PhotoshopMcpServer (Python process)             │
│  - dcc-mcp-core McpHttpServer                                │
│  - SkillCatalog (discovers skills from skills/)              │
│  - PhotoshopBridge client (connects to port 3000)            │
└───────────────────────────┬─────────────────────────────────┘
                            │ JSON-RPC 2.0 over WebSocket (port 3000)
┌───────────────────────────▼─────────────────────────────────┐
│              Photoshop UXP Plugin (JavaScript)               │
│  - WebSocket server (UXP network API)                        │
│  - JSON-RPC dispatcher                                       │
│  - Photoshop API handlers (documents, layers, filters...)    │
└───────────────────────────┬─────────────────────────────────┘
                            │ UXP API calls
┌───────────────────────────▼─────────────────────────────────┐
│                   Adobe Photoshop                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Communication Protocol

**Request** (Python → Photoshop):
```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "ps.listLayers",
  "params": {"include_hidden": true}
}
```

**Response** (Photoshop → Python):
```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": [
    {"name": "Background", "type": "pixel", "visible": true, "opacity": 100},
    {"name": "Layer 1",    "type": "pixel", "visible": true, "opacity": 75}
  ]
}
```

### 4.3 DccCapabilities Declaration

```python
DccCapabilities(
    has_embedded_python=False,     # No embedded Python
    bridge_kind="websocket",       # WebSocket bridge
    bridge_endpoint="ws://localhost:3000",
    snapshot=True,                 # Can capture viewport
    file_operations=True,          # Open/save/export
    scene_info=True,               # Document metadata
    selection=True,                # Selection manipulation
)
```

---

## 5. Skill Authoring Contract

Skill scripts in `skills/<name>/scripts/<action>.py` follow this pattern:

```python
from dcc_mcp_photoshop.api import get_bridge, ps_success, with_photoshop

@with_photoshop                        # auto error handling
def my_action(param: str = "default", **kwargs) -> dict:
    bridge = get_bridge()              # get WebSocket bridge
    result = bridge.call("ps.method", param=param)  # call UXP
    return ps_success("Done", data=result)          # return result

def main(**kwargs) -> dict:
    return my_action(**kwargs)

if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main
    run_main(main)
```

**Key differences from Maya/Unreal:**
- No `import photoshop` — use `bridge.call()` instead
- Bridge may raise `BridgeConnectionError` / `NotImplementedError`
- `@with_photoshop` catches `PhotoshopNotAvailableError` specifically

---

## 6. UXP Plugin Requirements

### 6.1 Photoshop Version Support
- Minimum: Photoshop 2022 (v23.0) — first stable UXP release
- Recommended: Photoshop 2024 (v25.0+) for latest UXP features

### 6.2 UXP API Surface Used
- `require('photoshop').app` — application object
- `require('photoshop').app.activeDocument` — active document
- `require('photoshop').action.batchPlay` — Action Manager
- `require('uxp').network` — WebSocket server

### 6.3 Permissions Required
```json
{
  "requiredPermissions": {
    "network": { "webSockets": "localhost" },
    "localFileSystem": "request"
  }
}
```

---

## 7. Testing Strategy

### Unit Tests (no Photoshop required)
- Bridge connection state management
- JSON-RPC message formatting
- Error handling paths (`@with_photoshop`, `PhotoshopNotAvailableError`)
- `ps_success` / `ps_error` / `ps_from_exception` result dicts
- Server instantiation and configuration

### Integration Tests (requires Photoshop)
- Mark with `@pytest.mark.e2e`
- Require `DCC_MCP_PHOTOSHOP_TEST=1` environment variable
- Test round-trip: Python → WebSocket → UXP → Photoshop → result

---

## 8. Security Considerations

- WebSocket server binds to `localhost` only (never public interface)
- UXP `localFileSystem` permission is `"request"` (user must approve)
- No external network access from the plugin
- `bridge.call()` accepts only whitelisted method names

---

## 9. Open Questions

1. **Auto-discovery**: Should the bridge auto-discover the UXP WebSocket port, or always use a fixed port?
2. **Authentication**: Should we add a shared secret / token to prevent other processes from connecting to the UXP plugin?
3. **Multi-document**: How to handle multiple open documents? Scope per-call, or maintain session state?
4. **Photoshop version detection**: Should the bridge negotiate capabilities based on detected PS version?
5. **Windows-only**: Initial implementation targets Windows. macOS support for UXP is similar but needs testing.

---

## 10. Milestones

| Milestone | Target | Deliverables |
|-----------|--------|-------------|
| v0.1.0 | Now | Project scaffold, bridge stub, UXP plugin stub |
| v0.2.0 | TBD | Real WebSocket + 3 working skills |
| v0.3.0 | TBD | 5 skill categories, production-ready |
| v1.0.0 | TBD | Full feature set, CI/CD, PyPI release |
