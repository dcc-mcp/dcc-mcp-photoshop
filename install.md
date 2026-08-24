# Requirements

- Adobe Photoshop 2022 or newer.
- Python 3.8 or newer for the wheel-based adapter path.
- `dcc-mcp-core` 0.20.14 or newer. The installed Core package must carry the
  canonical Install SOP v1 schema byte-for-byte.
- The supported adobepy CLI from an approved adobepy release or an exact tagged source build.
- Adobe UXP Developer Tool for the one Adobe-owned developer-plugin load step.

Install the adapter wheel first:

```bash
python -m pip install dcc-mcp-photoshop
```

The PyPI `adobepy` wheel is the Python SDK; it does not install the standalone
adobepy CLI. Windows operators can use the signed/checksummed release bundle.
macOS operators must use an organization-approved exact-tag build until an
official macOS CLI asset is published. Never scrape a mutable latest-download
URL or copy an unverified executable into an adapter cache.

Set the CLI path and broker token in the environment. The token is a secret and
must never be placed in process arguments, JSON output, logs, or receipts.

```powershell
$env:ADOBEPY_CLI = "C:\Tools\adobepy\adobepy.exe"
$env:ADOBEPY_TOKEN = (Get-Content "$env:USERPROFILE\.config\adobepy\token" -Raw).Trim()
```

```bash
export ADOBEPY_CLI="$HOME/.local/bin/adobepy"
export ADOBEPY_TOKEN="$(cat "$HOME/.config/adobepy/token")"
```

# Supported versions

| Platform | Photoshop host | Adapter lifecycle |
|---|---|---|
| Windows | Photoshop 2022+ under `Program Files/Adobe/Adobe Photoshop <year>/Photoshop.exe` | Supported |
| macOS | Photoshop 2022+ under `/Applications/Adobe Photoshop <year>/Adobe Photoshop <year>.app` | Supported when an approved adobepy CLI is supplied |
| Linux | Adobe does not ship a Photoshop desktop host | Plan/status tooling only; live verification is unsupported |

The canonical result uses Install SOP v1 schema version `1`. Exit codes are
`0` success, `10` preflight, `20` acquire, `30` install/rollback, `40` verify,
and `50` host restart or UXP load required.

# Agent quick path

Plan first. The command performs host, Python, Core, token-policy, existing-state,
and adobepy CLI preflight without changing files:

```bash
dcc-mcp-photoshop install --json --dry-run --dcc-path "/path/to/Photoshop" --python "/path/to/python"
```

Review the plan and apply it:

```bash
dcc-mcp-photoshop install --json --yes --dcc-path "/path/to/Photoshop" --python "/path/to/python"
```

The lifecycle generates the UXP bridge in a sibling staging directory, verifies
its manifest, atomically swaps it into the adapter-owned install root, and writes
a redacted receipt containing a complete typed file, directory, and link closure.
Fresh, partial, installed, repair, and upgrade states are reported explicitly.
Upgrade keeps its backup through live verification; any commit, receipt, or
verification failure restores the exact previous receipt-backed tree.

Adobe physically requires an explicit developer-plugin load. When no live UXP
session exists, the installer returns the manifest for that operator action and
an executable `adobepy doctor` command bound to the selected broker, Python, and
runtime. It does not claim a blind verify loop as progress and does not use UI
automation.

# Manual path

The supported manual flow uses the same canonical lifecycle:

1. Install the adapter wheel and an approved adobepy CLI.
2. Configure `ADOBEPY_CLI`, `ADOBEPY_TOKEN`, and optionally `ADOBEPY_BROKER_URL`.
3. Run `dcc-mcp-photoshop install --json --dry-run` with explicit overrides when discovery is ambiguous.
4. Run `dcc-mcp-photoshop install --json --yes`.
5. Load the staged manifest with Adobe UXP Developer Tool when requested.
6. Run `dcc-mcp-photoshop verify --json`.

The legacy `scripts/install_photoshop_connector.ps1` and `photoshop-setup`
Skill remain compatibility entry points, but both route operators to this CLI.
They no longer maintain a Windows-only registry/CCX installer. Current
dcc-mcp-photoshop releases do not contain a CCX artifact; the UXP bridge template
belongs to the separately released adobepy project.

# Verify

```bash
dcc-mcp-photoshop status --json
dcc-mcp-photoshop verify --json
```

Verification is ordered and fail-closed:

1. Validate the complete typed ownership closure and reject extra, escaped,
   duplicate, wrong-type, or tampered paths while preserving unowned content.
2. Import through the selected Python and prove adapter, Core, and adobepy
   origins against distribution metadata.
3. Verify the installed Core package's canonical Install SOP schema bytes.
4. Probe the authenticated adobepy broker and bind its PID, process-start
   identity, executable, version, and instance to independent OS observations.
5. Require exactly one matching Photoshop UXP session and a typed Photoshop RPC
   bound to the host PID/start/executable/profile and installed plugin origins.

Files copied is not an installed/usable result. Only the real Photoshop RPC can
set `verify.directly_usable` to `true`.

# Upgrade

Plan and apply an upgrade with the recorded host/interpreter or explicit
overrides:

```bash
dcc-mcp-photoshop upgrade --json --dry-run --dcc-path "/path/to/Photoshop" --python "/path/to/python"
dcc-mcp-photoshop upgrade --json --yes --dcc-path "/path/to/Photoshop" --python "/path/to/python"
```

Upgrade keeps the old bridge until the staged replacement is valid. A commit or
receipt failure restores the previous tree. Loaded native artifacts return exit
`50`; restart Photoshop and retry the exact command.

# Uninstall

```bash
dcc-mcp-photoshop uninstall --json --dry-run
dcc-mcp-photoshop uninstall --json --yes
```

Uninstall consumes only the adapter receipt and refuses an unknown path. It
does not delete a guessed UXP, Adobe, or user profile directory, and it stages a
recoverable snapshot before removing anything. Any staging, receipt, or cleanup
failure restores the complete install; locked files return exit `50` with a
retry command after Photoshop restarts.

# Troubleshooting

- **Exit `10`, host not found:** pass the full Photoshop executable with `--dcc-path`; Photoshop 2022+ is required.
- **Exit `10`, interpreter/Core floor:** pass a Python 3.8+ executable and upgrade `dcc-mcp-core` to the reported minimum.
- **Exit `20`, adobepy CLI missing:** set `ADOBEPY_CLI` to a supported, verified executable. The SDK-only wheel is not a CLI substitute.
- **Exit `30`, bridge staging:** inspect the redacted stage result. External output containing the configured token is rejected and discarded.
- **Exit `40`, verification:** start the broker, confirm one Photoshop UXP session, and retry `dcc-mcp-photoshop verify --json`.
- **Exit `50`, UXP load required:** load the reported manifest with Adobe UXP Developer Tool, or restart Photoshop when files are locked, then run the single returned command.
- **Partial state:** run `dcc-mcp-photoshop install --json --yes` to repair it. Do not delete the bridge before repair.
- **Bootstrap failure:** inspect the bounded, secret-redacted `bootstrap-errors.json` under the Photoshop install state directory.

Core 0.20.14 owns the canonical schema and exit contract. Adapter contract tests
validate every public lifecycle branch against that Draft 2020-12 schema; the
adapter remains the owner of Photoshop paths, UXP enablement, receipts, and
exact-instance runtime verification. adobepy 0.6.2 does not yet expose the full
broker and host identity attestation, so live verification remains fail-closed
until that upstream contract is available; staging and package tests are not
proof of a licensed Photoshop session.
