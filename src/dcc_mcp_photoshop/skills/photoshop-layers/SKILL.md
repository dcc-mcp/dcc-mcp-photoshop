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
actually looks like, not what the layer properties claim.

`verify_layer_batch` toggles visibility while it runs, so it is **not** a
read-only tool.

## Reading the report

`no_op` is tri-state, and only `true` means "measured and invisible":

| `no_op` | meaning |
| --- | --- |
| `true` | measured: the layer changes nothing (`ok`), or it is hidden / zero-area |
| `false` | measured: the layer does change the composite |
| `null` | **unknown** — the probe could not measure this layer, so nothing is claimed |

A `null` never reaches `no_op_layers`. The report separates the outcomes so an
unsampleable layer is never mistaken for a clean one:

- `no_op_layers` — measured, contributes nothing. Safe to act on.
- `inconclusive_layers` — `status` is `unsupported`, `error`, `missing` or
  `no_bounds`. Coverage gap, not a pass.
- `unrestored_layers` — the probe could not show these layers again; check them
  before continuing.

Each per-layer report also carries `visibility_restored`. If restoring
visibility fails, the layer is reported as `status: "error"` with
`visibility_restored: false` rather than a normal verdict — a layer silently
left hidden is the one side effect this probe can leave behind.

Layer groups are walked into, so layers nested inside a group are covered by
the default scan rather than reported as missing.
