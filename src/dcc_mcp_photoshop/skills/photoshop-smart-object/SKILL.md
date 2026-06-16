---
name: photoshop-smart-object
description: "Adobe Photoshop Smart Object operations — convert, copy, edit, and replace"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, smart-object, non-destructive, adobe]
search-hint: "convert to smart object, new via copy, edit contents, replace contents, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: convert_to_smart_object
    description: "Convert the active layer to a Smart Object"
    source_file: scripts/convert_to_smart_object.py
    read_only: false
    destructive: false
    idempotent: false
  - name: new_smart_object_via_copy
    description: "Create a new Smart Object by duplicating the active layer"
    source_file: scripts/new_smart_object_via_copy.py
    read_only: false
    destructive: false
    idempotent: false
  - name: edit_smart_object_contents
    description: "Open the Smart Object in a new document for editing"
    source_file: scripts/edit_smart_object_contents.py
    read_only: false
    destructive: false
    idempotent: false
  - name: replace_smart_object_contents
    description: "Replace Smart Object contents with an external file"
    source_file: scripts/replace_smart_object_contents.py
    read_only: false
    destructive: false
    idempotent: true
---

# photoshop-smart-object

Adobe Photoshop Smart Object operations via the adobepy broker.

## Tools

- `convert_to_smart_object` — Convert layer to Smart Object
- `new_smart_object_via_copy` — Duplicate layer as new Smart Object
- `edit_smart_object_contents` — Open Smart Object for editing
- `replace_smart_object_contents` — Replace with external file
