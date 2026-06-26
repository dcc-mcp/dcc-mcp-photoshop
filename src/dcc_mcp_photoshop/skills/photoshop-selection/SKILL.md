---
name: photoshop-selection
description: "Adobe Photoshop selection operations — get, create, modify, and save selections"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, selection, marquee, adobe]
search-hint: "select all, deselect, inverse, rectangle, ellipse, expand, contract, feather, save selection, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: get_selection
    description: "Get current selection bounds (top, left, bottom, right)"
    source_file: scripts/get_selection.py
    read_only: true
    destructive: false
    idempotent: true
  - name: select_all
    description: "Select the entire canvas"
    source_file: scripts/select_all.py
    read_only: false
    destructive: false
    idempotent: true
  - name: deselect
    description: "Deselect any active selection"
    source_file: scripts/deselect.py
    read_only: false
    destructive: false
    idempotent: true
  - name: select_rectangle
    description: "Create a rectangular selection (top, left, bottom, right in pixels)"
    source_file: scripts/select_rectangle.py
    read_only: false
    destructive: false
    idempotent: true
  - name: select_ellipse
    description: "Create an elliptical selection (top, left, bottom, right in pixels)"
    source_file: scripts/select_ellipse.py
    read_only: false
    destructive: false
    idempotent: true
  - name: inverse_selection
    description: "Invert the current selection"
    source_file: scripts/inverse_selection.py
    read_only: false
    destructive: false
    idempotent: true
  - name: expand_selection
    description: "Expand the current selection by N pixels"
    source_file: scripts/expand_selection.py
    read_only: false
    destructive: false
    idempotent: true
  - name: contract_selection
    description: "Contract the current selection by N pixels"
    source_file: scripts/contract_selection.py
    read_only: false
    destructive: false
    idempotent: true
  - name: feather_selection
    description: "Feather the current selection by N pixels"
    source_file: scripts/feather_selection.py
    read_only: false
    destructive: false
    idempotent: true
  - name: save_selection
    description: "Save the current selection as a named alpha channel"
    source_file: scripts/save_selection.py
    read_only: false
    destructive: false
    idempotent: false
---

# photoshop-selection

Adobe Photoshop selection operations via the adobepy broker.

## Tools

- `get_selection` — Get current selection bounds
- `select_all` — Select entire canvas
- `deselect` — Clear active selection
- `select_rectangle` — Create rectangular marquee (top/left/bottom/right)
- `select_ellipse` — Create elliptical marquee (top/left/bottom/right)
- `inverse_selection` — Invert current selection
- `expand_selection` — Expand selection by N pixels
- `contract_selection` — Contract selection by N pixels
- `feather_selection` — Feather selection by N pixels
- `save_selection` — Save selection as alpha channel
