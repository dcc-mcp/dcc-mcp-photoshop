---
name: photoshop-image
description: "Adobe Photoshop image operations — create new documents, export, resize canvas, flatten, merge layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, image, document, export, resize, flatten, adobe]
search-hint: "create document new canvas export png jpg resize flatten merge photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: create_document
    description: "Create a new Photoshop document with specified dimensions, resolution and color mode."
    source_file: scripts/create_document.py
    read_only: false
    destructive: false
    idempotent: false
  - name: export_document
    description: "Export the active document to a file (PNG, JPG, TIFF, PSD). Returns the output path."
    source_file: scripts/export_document.py
    read_only: false
    destructive: false
    idempotent: true
  - name: save_document
    description: "Save the active Photoshop document in its current format."
    source_file: scripts/save_document.py
    read_only: false
    destructive: false
    idempotent: true
  - name: resize_canvas
    description: "Resize the canvas of the active document (changes document dimensions without scaling content)."
    source_file: scripts/resize_canvas.py
    read_only: false
    destructive: false
    idempotent: true
  - name: resize_image
    description: "Scale the active document to new dimensions (resamples content)."
    source_file: scripts/resize_image.py
    read_only: false
    destructive: false
    idempotent: true
  - name: flatten_image
    description: "Flatten all layers in the active document into a single background layer."
    source_file: scripts/flatten_image.py
    read_only: false
    destructive: true
    idempotent: true
  - name: merge_visible_layers
    description: "Merge all visible layers in the active document."
    source_file: scripts/merge_visible_layers.py
    read_only: false
    destructive: true
    idempotent: true
---

# photoshop-image

Image-level operations for Adobe Photoshop: create documents, export to
various formats, resize canvas/image, and merge/flatten layers.

## Tools

- `create_document` — New document with custom size, resolution, color mode
- `export_document` — Export as PNG / JPG / TIFF / PSD
- `save_document` — Save in place
- `resize_canvas` — Change canvas size without resampling
- `resize_image` — Scale the image (resamples)
- `flatten_image` — Flatten to single layer
- `merge_visible_layers` — Merge visible layers
