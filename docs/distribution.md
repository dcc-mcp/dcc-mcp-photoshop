# Distribution Guide

dcc-mcp-photoshop and adobepy are separate release trains with separate
ownership boundaries.

| Component | Source | Responsibility |
|---|---|---|
| dcc-mcp-photoshop wheel and standalone binaries | dcc-mcp-photoshop releases | MCP adapter, built-in skills, gateway registration |
| adobepy executable and Python SDK | adobepy releases | Broker, protocol, Photoshop facade |
| adobepy Photoshop UXP bridge template | adobepy releases | In-host execution and capability advertisement |

The dcc-mcp-photoshop repository does not own or publish a Photoshop `.ccx`.
Development bridge registration and loading remain explicit Adobe workflows.
The current release assets confirm this boundary: adapter archives and Python
packages are published here, while the UXP bridge template is owned by
adobepy.

## Install

Use the canonical agent runbook:

https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-photoshop/main/install.md

It owns all standard verbs, env-only authentication, staging, receipt,
rollback, Adobe host enablement, and real Photoshop RPC verification. This
distribution guide intentionally does not duplicate that host-specific
lifecycle.

## Release artifacts

A dcc-mcp-photoshop release publishes:

- `dcc_mcp_photoshop-<version>-py3-none-any.whl`
- `dcc_mcp_photoshop-<version>.tar.gz`
- platform-specific standalone adapter archives

The matching adobepy release publishes the broker executable, Python SDK, and
UXP bridge templates. Do not claim a bridge is installed merely because files
were copied: the Adobe host load and a real Photoshop RPC are the acceptance
checks.

## Release process

1. Merge a conventional commit to `main`.
2. Let release-please update the release PR.
3. Merge the release PR after CI passes.
4. Verify the tag, PyPI artifact, standalone archives, and live broker/bridge
   session independently.
