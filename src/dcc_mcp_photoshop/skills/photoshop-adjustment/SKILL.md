---
name: photoshop-adjustment
description: "Adobe Photoshop adjustment and batch operations — channels and batchPlay"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, adjustment, channel, batchplay, adobe]
search-hint: "batch play, channels, add channel, remove channel, action descriptor, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: batch_play
    description: "Execute raw ActionDescriptor batchPlay commands for advanced Photoshop operations"
    source_file: scripts/batch_play.py
    read_only: false
    destructive: false
    idempotent: false
  - name: get_channels
    description: "Get channel information for the active document"
    source_file: scripts/get_channels.py
    read_only: true
    destructive: false
    idempotent: true
  - name: add_channel
    description: "Add a new alpha channel to the active document"
    source_file: scripts/add_channel.py
    read_only: false
    destructive: false
    idempotent: false
  - name: remove_channel
    description: "Remove a named channel from the active document"
    source_file: scripts/remove_channel.py
    read_only: false
    destructive: true
    idempotent: false
---

# photoshop-adjustment

Adobe Photoshop adjustment and batch operations via the adobepy broker.

## Tools

- `batch_play` — Execute raw ActionDescriptor batchPlay commands
- `get_channels` — List document channels (active and component)
- `add_channel` — Create a new alpha channel
- `remove_channel` — Delete a named channel
