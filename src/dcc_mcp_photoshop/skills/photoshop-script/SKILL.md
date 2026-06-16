---
name: photoshop-script
description: "Execute JavaScript scripts and Photoshop Actions"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, script, action, batchplay, javascript]
search-hint: "execute script, execute action, batch play, run javascript, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: execute_script
    description: "Execute arbitrary JavaScript/UXP code in Photoshop. Use for advanced operations not covered by typed tools."
    source_file: scripts/execute_script.py
    read_only: false
    destructive: false
    idempotent: false
  - name: execute_action
    description: "Execute a named Photoshop Action from an Action Set via batchPlay."
    source_file: scripts/execute_action.py
    read_only: false
    destructive: false
    idempotent: false
---

# photoshop-script

Execute JavaScript scripts and Photoshop Actions via the adobepy broker.

## Tools

- `execute_script` — Run arbitrary JavaScript/UXP code in Photoshop
- `execute_action` — Execute a named Photoshop Action from an Action Set
