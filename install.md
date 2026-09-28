# Requirements

- Adobe Photoshop 2022 or newer.
- Python 3.8 or newer for the wheel-based adapter path.
- `dcc-mcp-core>=0.20.14,<0.21.0`. The installed Core package must carry the
  canonical Install SOP v1 schema byte-for-byte. Core republishes that file under
  the same `-v1` revision id, so the adapter pins the expected bytes per Core
  release (`CORE_SCHEMA_ANCHORS` in
  `src/dcc_mcp_photoshop/install_contract.py`) instead of one global literal;
  Core releases newer than `CORE_SCHEMA_ANCHOR_MEASURED_THROUGH` verify without
  a pinned digest.
- On Windows x64, the exact `adobepy` 0.6.2 CLI from the official checksummed
  release bundle. Other CLI builds and self-authored adjacent manifests are not
  accepted as provenance.

Install the adapter wheel first:

```bash
python -m pip install dcc-mcp-photoshop
```

The PyPI `adobepy` wheel is the Python SDK; it does not install the standalone
adobepy CLI. The lifecycle currently recognizes only the official Windows x64
0.6.2 checksum release: archive SHA-256 `9ef9abb5e034359f12e9ce248b0030e38d34c76df343eb2713f18036068719a7`.
It independently pins the extracted CLI and package-manifest hashes and checks
them again immediately before execution. Never scrape a mutable latest-download
URL or copy an unverified executable beside a locally written manifest.

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

## Repackaged and portable hosts

Package managers that distribute Photoshop as a portable payload rewrite the host
bytes, so `Get-AuthenticodeSignature` reports `HashMismatch` instead of `Valid`
even though the signer subject and product metadata are genuine Adobe values.
Preflight treats that as fatal by default, because a tampered file and a forged
signature blob that merely embeds Adobe's public certificate are
indistinguishable at this layer: without a matching hash, neither the signed
digest nor the version resource proves anything.

When you own the host and accept that risk, opt in explicitly:

```bash
dcc-mcp-photoshop install --json --dry-run --allow-unverified-host \
  --dcc-path "/path/to/Photoshop.exe" --python "/path/to/python"
```

The same opt-in is available as `DCC_MCP_PHOTOSHOP_ALLOW_UNVERIFIED_HOST=1` for
non-interactive runners that cannot extend the command line. The opt-in only
relaxes the hash check: an unsigned host, a non-Adobe signer, or foreign product
metadata still fails closed, and the accepted risk is recorded as a
`host_signature_hash_mismatch` entry in the report `warnings` array and as
`plan.host.signature: authenticode_hash_mismatch`.

Portable payloads are not under `%ProgramFiles%/Adobe`, so auto-discovery needs
to be told where to look. Point it at the package root with
os.pathsep-separated entries:

```powershell
$env:DCC_MCP_PHOTOSHOP_HOST_ROOTS = "C:\Tools\portable;D:\apps\photoshop"
```

```bash
export DCC_MCP_PHOTOSHOP_HOST_ROOTS="/opt/photoshop:/srv/apps/photoshop"
```

Discovery then also recognizes versioned `bin/Photoshop.exe` layouts below those
roots, for example `<root>/portable_photoshop/26.10/bin/Photoshop.exe`. Passing
`--dcc-path` remains an exact override and wins over discovery.

Layout names are compared on one scale before any ordering happens: a release
year is mapped to its product major (`Adobe Photoshop 2024` and `2024` both rank
as 25), and a package directory of the form `<year>.<major>.<minor>.<patch>`
ranks by the components after the year (`2025.26.5.0` ranks as 26.5.0). Every
component counts, so `26.10` outranks `26.9`, and a portable payload outranks an
older conventional install. Directory order only breaks genuine ties.

## Internal prebuilt bridge deployment

An Internal workstation image may provide an already-built and approved UXP
bridge. The current `dcc-mcp-cli install` contract does not expose a bridge
source or Adobe debug-root option, so this adapter must not document or invoke
undocumented `--plugin-source`, `--adobe-debug-root`,
`DCC_MCP_PLUGIN_SOURCE`, or `DCC_MCP_ADOBE_DEBUG_ROOT` bindings.

Use the approved studio deployment tooling to create the directory link in
Photoshop's Adobe debug-plugin root, then skip the adapter install commands
below. Restart Photoshop after linking and wait for the bridge to load before
running `dcc-mcp-cli list`, `dcc-mcp-cli wait-ready --dcc-type photoshop`, and
`dcc-mcp-photoshop verify --json`. A link on disk is not live readiness.

The adapter-owned lifecycle below is the non-Internal path for generated
bridges, receipt ownership, upgrades, and uninstall.

# Supported versions

| Platform | Photoshop host | Adapter lifecycle |
|---|---|---|
| Windows | Photoshop 2022+ with valid Adobe Authenticode and Photoshop product metadata. A repackaged or package-managed host whose signature hash no longer matches is rejected unless an operator accepts it (see [Repackaged and portable hosts](#repackaged-and-portable-hosts)) | Preflight/staging supported with the pinned adobepy 0.6.2 CLI; live readiness remains fail-closed on `adobepy#64` and `#67` |
| macOS | Photoshop 2022+ with `com.adobe.Photoshop` Info.plist and Adobe Team ID `JQ525L2MZD` code signature | Preflight only until an official checksum-pinned macOS adobepy CLI is published |
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

The current adobepy release cannot perform a bounded Photoshop UXP bootstrap or
load. When no exact live UXP session exists, the installer returns an honest
`bounded_photoshop_uxp_bootstrap_unavailable` blocker, an empty `next_steps`, and
the exact `dcc-mcp-photoshop verify --json` continuation for use only after the
upstream capability is delivered. It does not claim `doctor` or a blind verify
loop as progress and does not automate arbitrary UI or JavaScript.

# Manual path

The supported manual flow uses the same canonical lifecycle:

1. Install the adapter wheel and an approved adobepy CLI.
2. Configure `ADOBEPY_CLI`, `ADOBEPY_TOKEN`, and optionally `ADOBEPY_BROKER_URL`.
3. Run `dcc-mcp-photoshop install --json --dry-run` with explicit overrides when discovery is ambiguous.
4. Run `dcc-mcp-photoshop install --json --yes`.
5. Wait for the bounded adobepy Photoshop UXP bootstrap/load capability tracked
   in `dcc-mcp/adobepy#67`; do not substitute arbitrary UI automation.
6. After that capability binds the exact instance, run the reported
   `dcc-mcp-photoshop verify --json` continuation.

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
stable reason so the same exact uninstall command can be rerun after Photoshop
restarts.
Running confirmed uninstall again in the already-absent state is a schema-valid
successful no-op.

# Troubleshooting

- **Exit `10`, host not found/untrusted:** pass the full Photoshop executable with `--dcc-path`; the lifecycle requires nonempty Adobe-signed product bytes and derives the version from product metadata rather than the directory name.
- **Exit `10`, host signature `HashMismatch`:** the host was repackaged. Reinstall an untouched Adobe build when provenance matters; otherwise opt in with `--allow-unverified-host` (or `DCC_MCP_PHOTOSHOP_ALLOW_UNVERIFIED_HOST=1`) and review the `warnings` array. See [Repackaged and portable hosts](#repackaged-and-portable-hosts).
- **Host not discovered:** set `DCC_MCP_PHOTOSHOP_HOST_ROOTS` to the portable package root, or pass `--dcc-path`.
- **Exit `10`, interpreter/Core floor:** pass a Python 3.8+ executable and upgrade `dcc-mcp-core` to the reported minimum.
- **Exit `20`, adobepy CLI missing:** set `ADOBEPY_CLI` to the exact executable extracted from the pinned official Windows 0.6.2 checksum release. The SDK-only wheel, a source build, or an adjacent local manifest is not a substitute.
- **Exit `30`, bridge staging:** inspect the redacted stage result. External output containing the configured token is rejected and discarded.
- **Exit `40`, verification:** start the broker, confirm one Photoshop UXP session, and retry `dcc-mcp-photoshop verify --json`.
- **Exit `50`, UXP load required:** the lifecycle fails closed with the `dcc-mcp/adobepy#67` blocker until bounded bootstrap/load exists. A file-lock restart is separate and may be retried after the operator resolves the lock.
- **Partial state:** run `dcc-mcp-photoshop install --json --yes` to repair it. Do not delete the bridge before repair.
- **Bootstrap failure:** inspect the bounded, secret-redacted `bootstrap-errors.json` under the Photoshop install state directory.

Core `>=0.20.14,<0.21.0` owns the canonical schema and exit contract. Adapter contract tests
validate every public lifecycle branch against that Draft 2020-12 schema; the
adapter remains the owner of Photoshop paths, UXP enablement, receipts, and
exact-instance runtime verification. adobepy runtime identity remains tracked in
`dcc-mcp/adobepy#64`, and bounded Photoshop UXP bootstrap/load in `#67`; live
verification remains fail-closed until both contracts are available. Staging,
package, and checksum tests are not proof of a licensed Photoshop session.
