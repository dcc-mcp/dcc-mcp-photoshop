---
name: photoshop-text
description: "Adobe Photoshop text layer operations — create, edit, style text layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, text, typography, font, adobe]
search-hint: "text layer create font size color bold italic photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: create_text_layer
    description: "Create a new text layer in the active document with specified content and styling."
    source_file: scripts/create_text_layer.py
    read_only: false
    destructive: false
    idempotent: false
  - name: update_text_layer
    description: "Update the text content or style of an existing text layer."
    source_file: scripts/update_text_layer.py
    read_only: false
    destructive: false
    idempotent: true
  - name: get_text_layer_info
    description: "Get the text content and style properties of a text layer."
    source_file: scripts/get_text_layer_info.py
    read_only: true
    destructive: false
    idempotent: true
---

# photoshop-text

Text layer operations for Adobe Photoshop. Create and edit text layers with
full font, size, color, and alignment control.

## Tools

- `create_text_layer` — Add a new text layer with full styling
- `update_text_layer` — Change text content or style of an existing layer
- `get_text_layer_info` — Read text properties (font, size, color, etc.)
