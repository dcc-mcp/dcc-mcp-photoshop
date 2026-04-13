---
name: photoshop-layers
description: "Adobe Photoshop layer operations — create, delete, reorder, duplicate, rename, set opacity/visibility, fill, blend modes"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, layers, opacity, visibility, blend, adobe]
search-hint: "layer create delete rename duplicate opacity blend mode fill group"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: create_layer
    description: "Create a new pixel, group, or adjustment layer in the active document."
    source_file: scripts/create_layer.py
    read_only: false
    destructive: false
    idempotent: false
  - name: delete_layer
    description: "Delete a named layer from the active document."
    source_file: scripts/delete_layer.py
    read_only: false
    destructive: true
    idempotent: false
  - name: duplicate_layer
    description: "Duplicate a named layer, optionally giving the duplicate a new name."
    source_file: scripts/duplicate_layer.py
    read_only: false
    destructive: false
    idempotent: false
  - name: rename_layer
    description: "Rename a layer in the active document."
    source_file: scripts/rename_layer.py
    read_only: false
    destructive: false
    idempotent: true
  - name: set_layer_opacity
    description: "Set the opacity (0-100) of a named layer."
    source_file: scripts/set_layer_opacity.py
    read_only: false
    destructive: false
    idempotent: true
  - name: set_layer_visibility
    description: "Show or hide a named layer."
    source_file: scripts/set_layer_visibility.py
    read_only: false
    destructive: false
    idempotent: true
  - name: set_layer_blend_mode
    description: "Set the blend mode of a named layer (normal, multiply, screen, overlay, etc.)."
    source_file: scripts/set_layer_blend_mode.py
    read_only: false
    destructive: false
    idempotent: true
  - name: fill_layer
    description: "Fill a layer with a solid color (hex or RGB) or transparent."
    source_file: scripts/fill_layer.py
    read_only: false
    destructive: false
    idempotent: true
---

# photoshop-layers

Layer management skill for Adobe Photoshop. Provides complete CRUD operations
on document layers plus visual property changes (opacity, blend mode, fill).

## Tools

- `create_layer` — Create pixel / group layer
- `delete_layer` — Delete a layer by name
- `duplicate_layer` — Duplicate a layer
- `rename_layer` — Rename a layer
- `set_layer_opacity` — Change opacity 0-100
- `set_layer_visibility` — Show / hide
- `set_layer_blend_mode` — Change blend mode
- `fill_layer` — Fill with solid color
