---
name: photoshop-document
description: "Adobe Photoshop document management — query, list, and close documents and layers"
dcc: photoshop
version: "0.2.0"
tags: [photoshop, document, layers, adobe]
search-hint: "document info, list documents, list layers, close document, photoshop"
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
  - name: list_documents
    description: "List all currently open Photoshop documents with metadata (name, path, dimensions)"
    source_file: scripts/list_documents.py
    read_only: true
    destructive: false
    idempotent: true
  - name: list_layers
    description: "List all layers in the active Photoshop document. Set include_hidden=false to exclude hidden layers."
    source_file: scripts/list_layers.py
    read_only: true
    destructive: false
    idempotent: true
  - name: close_document
    description: "Close a Photoshop document by ID or the active document. Optionally save before closing."
    source_file: scripts/close_document.py
    read_only: false
    destructive: true
    idempotent: false
---

# photoshop-document

Adobe Photoshop document management skill. Uses the adobepy broker to communicate with Photoshop.

## Tools

- `get_document_info` — Get name, dimensions, resolution, color mode of the active document
- `list_documents` — List all open documents with metadata
- `list_layers` — List all layers (with optional hidden layer filter)
- `close_document` — Close a document by ID or close active document
