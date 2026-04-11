---
name: photoshop-document
description: "Adobe Photoshop document management — open, save, create, and query documents"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, document, layers, adobe]
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
---

# photoshop-document

Adobe Photoshop document management skill. Uses the WebSocket bridge to communicate with Photoshop via the UXP plugin.

## Scripts

- `get_document_info` — Get information about the active Photoshop document
- `list_documents` — List all open documents
- `list_layers` — List all layers in the active document
- `create_layer` — Create a new layer in the active document
- `export_document` — Export the active document to a file
