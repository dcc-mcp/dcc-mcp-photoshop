---
name: photoshop-filter
description: "Adobe Photoshop filter operations — apply blur, sharpen, and other filters to layers"
dcc: photoshop
version: "0.1.0"
tags: [photoshop, filter, blur, sharpen, adobe]
search-hint: "gaussian blur, high pass, sharpen, smart blur, apply filter, photoshop"
license: "MIT"
allowed-tools: ["Bash", "Read"]
depends: []
tools:
  - name: apply_gaussian_blur
    description: "Apply Gaussian Blur filter to the active layer"
    source_file: scripts/apply_gaussian_blur.py
    read_only: false
    destructive: false
    idempotent: true
  - name: apply_high_pass
    description: "Apply High Pass filter to the active layer"
    source_file: scripts/apply_high_pass.py
    read_only: false
    destructive: false
    idempotent: true
  - name: apply_sharpen
    description: "Apply Sharpen filter to the active layer"
    source_file: scripts/apply_sharpen.py
    read_only: false
    destructive: false
    idempotent: true
  - name: apply_smart_blur
    description: "Apply Smart Blur filter with radius and threshold"
    source_file: scripts/apply_smart_blur.py
    read_only: false
    destructive: false
    idempotent: true
  - name: apply_filter
    description: "Apply a generic filter by method name with optional arguments"
    source_file: scripts/apply_filter.py
    read_only: false
    destructive: false
    idempotent: true
---

# photoshop-filter

Adobe Photoshop filter operations via the adobepy broker.

## Tools

- `apply_gaussian_blur` — Apply Gaussian Blur (radius in pixels)
- `apply_high_pass` — Apply High Pass filter (radius in pixels)
- `apply_sharpen` — Apply Sharpen filter
- `apply_smart_blur` — Apply Smart Blur (radius + threshold)
- `apply_filter` — Generic filter by method name
