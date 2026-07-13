---
name: photoshop-script
description: Execute JavaScript scripts and Photoshop Actions
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
    - script
    - action
    - batchplay
    - javascript
    search-hint: execute script, execute action, batch play, run javascript, photoshop
    tools: tools.yaml
---
# photoshop-script

Execute JavaScript scripts and Photoshop Actions via the adobepy broker.

## Tools

- `execute_script` — Run arbitrary JavaScript/UXP code in Photoshop
- `execute_action` — Execute a named Photoshop Action from an Action Set
