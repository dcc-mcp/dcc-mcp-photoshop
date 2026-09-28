---
name: photoshop-layers
description: Adobe Photoshop layer operations — create, delete, reorder, duplicate, rename, set opacity/visibility, fill,
  blend modes
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
    - layers
    - opacity
    - visibility
    - blend
    - adobe
    search-hint: layer create delete rename duplicate opacity blend mode fill group
    tools: tools.yaml
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
- `verify_layer_batch` — Report layers that contribute nothing to the composite

## Silent no-ops

A layer write can succeed while being mathematically invisible. `overlay` over a
solid white backdrop evaluates to exactly white again, so the layer disappears
from the composite even though every layer property reports the value that was
requested. Opacity `0`, a hidden layer, and a fully masked-out layer behave the
same way.

None of these raise an error, so a batch run can produce a document that looks
correct and is missing content. Two entry points make the no-op measurable
rather than silent:

- `set_layer_blend_mode` and `set_layer_opacity` accept `verify` (default
  `true`). They then return an `effect` block with `no_op`, `max_delta` and a
  human-readable `reason`. Pass `verify: false` to skip the read-back.
- `verify_layer_batch` checks a whole batch in one call and returns
  `no_op_layers`. Use it after a batch of writes instead of verifying one layer
  at a time.

The probe samples the composite inside each layer's bounds, hides the layer,
samples again, and restores visibility — so it measures what the document
actually looks like, not what the layer properties claim. When the host cannot
provide composite pixels, the report carries `status: "unsupported"` and
`no_op: null` instead of guessing.
