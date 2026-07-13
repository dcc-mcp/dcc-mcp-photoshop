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

## Install

```powershell
pip install dcc-mcp-photoshop

# From an extracted adobepy release bundle:
adobepy broker
adobepy install-bridge photoshop --dest "$env:LOCALAPPDATA\adobepy\bridges\photoshop"
```

Enable Developer Mode in Photoshop. Open Adobe UXP Developer Tool, add the
generated `manifest.json`, and click **Load**. The broker health endpoint must
then report at least one session.

Start the adapter after the broker and bridge are ready:

```powershell
dcc-mcp-photoshop --mcp-port 8765 --gateway-port 9765
```

Clients should use the gateway endpoint `http://127.0.0.1:9765/mcp` or the
direct adapter endpoint `http://127.0.0.1:8765/mcp`.

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
