---
name: photoshop-text
description: Adobe Photoshop text layer operations — create, edit, style text layers
license: MIT
allowed-tools:
- Bash
- Read
metadata:
  dcc-mcp:
    dcc: photoshop
    version: 0.1.0
    layer: domain
    tags:
    - photoshop
    - text
    - typography
    - font
    - adobe
    search-hint: text layer create font size color bold italic photoshop
    tools: tools.yaml
---
# photoshop-text

Text layer operations for Adobe Photoshop. Create and edit text layers with
full font, size, color, and alignment control.

## Tools

- `create_text_layer` — Add a new text layer with full styling
- `update_text_layer` — Change text content or style of an existing layer
- `get_text_layer_info` — Read text properties (font, size, color, etc.)
