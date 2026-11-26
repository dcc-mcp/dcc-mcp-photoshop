---
name: photoshop-smart-object
description: Adobe Photoshop Smart Object operations — convert, copy, edit, and replace
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
    - smart-object
    - non-destructive
    - adobe
    search-hint: convert to smart object, new via copy, edit contents, replace contents, photoshop
    tools: tools.yaml
---
# photoshop-smart-object

Adobe Photoshop Smart Object operations via the adobepy broker.

## Tools

- `convert_to_smart_object` — Convert layer to Smart Object
- `new_smart_object_via_copy` — Duplicate layer as new Smart Object
- `edit_smart_object_contents` — Open Smart Object for editing
- `replace_smart_object_contents` — Replace with external file
