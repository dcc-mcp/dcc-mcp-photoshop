---
name: photoshop-document
description: "Adobe Photoshop document management — open, save, create, and query documents and layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, document, layers, adobe]
search-hint: "document info, list layers, open, save, export, create layer, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: get_document_info
    description: "Get metadata about the active Photoshop document (name, size, resolution, color mode)"
    source_file: scripts/get_document_info.py
    read_only: true
    destructive: false
    idempotent: true
  - name: list_layers
    description: "List all layers in the active Photoshop document. Set include_hidden=false to exclude hidden layers."
    source_file: scripts/list_layers.py
    read_only: true
    destructive: false
    idempotent: true
---

# photoshop-document

Adobe Photoshop document management skill. Uses the WebSocket bridge to communicate with Photoshop via the UXP plugin.

## Tools

- `get_document_info` — Get name, dimensions, resolution, color mode of the active document
- `list_layers` — List all layers (with optional hidden layer filter)
