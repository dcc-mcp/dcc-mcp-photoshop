# UXP plugin auto-deploy design

This document records the product model, a survey of other Adobe MCP
implementations, the concrete gap in this adapter, and a staged plan to reach a
single-command, zero-extra-dependency deployment. It is a design record, not a
release note: every implementation step below is delivered as its own change
under the repository's normal review and CI gates.

## Product model

The supported path should be as small as the host allows:

1. Photoshop is installed and can load a UXP plugin.
2. One setup step registers and loads the adapter's UXP bridge plugin.
3. From then on the plugin connects at host startup, and Photoshop capabilities
   are callable through the MCP server with no per-session manual loading.

The same shape should hold for the other Adobe hosts. Extra user-side tools
(UXP Developer Tools, GUI drivers, a separately managed Python runtime, manual
token-file editing) are development conveniences or fallbacks, not prerequisites
of the supported install.

## How other Adobe MCP implementations do it

The survey covered the sibling adapters in this organization and the public
Adobe/Photoshop MCP projects. They converge on the same architecture.

**Sibling UXP / CEP adapters.** `dcc-mcp-premiere` stages a UXP bridge (manifest
v5, `host.app == "PR"`) and registers it with an idempotent directory link into
Adobe's UXP debug plugin directory (`dcc-mcp-cli install --plugin-source ...
--adobe-debug-root ... --execute`). That path does not require UXP Developer
Tools: the operator enables Adobe UXP debug mode once, restarts the host, and the
plugin loads on startup. `dcc-mcp-cli wait-ready --dcc-type premiere` then gates
readiness. `dcc-mcp-aftereffects` uses the equivalent CEP extension link into the
Adobe CEP extensions directory. Both keep plugin registration and loading as a
host-side fact and the broker/session handshake as an adapter-side fact; neither
pretends a trusted session exists before the host has actually loaded the plugin.

**Public Photoshop MCP projects.** The leading community implementations
(for example `alisaitteke/photoshop-mcp`, `Immersive-Media-Technologies/
photoshop-mcp-imt`, `airtaxi/PhotoshopMcpServer`) all put a host-side plugin or
automation surface in front of a local MCP server. Installation is a one-time
plugin/bridge setup plus one MCP client configuration; the server then starts
and calls host capabilities directly. Where a UXP bridge is used, it is there to
serve real host calls, and the Windows COM-based variants are an alternative
host-automation choice, not an additional user dependency. UXP Developer Tools
appears only as a developer fallback.

**Converged pattern.** `host plugin (UXP/CEP) + local broker/bridge + MCP
server`, with a one-time plugin registration, host restart, and readiness wait.
**No implementation** we surveyed establishes a trusted UXP session purely from
the installer side, and the After Effects adapter explicitly documents that
exact host identity remains unverified until a CEP launch-receipt/bootstrap path
exists. That boundary is real and is kept below.

## Current gap in this adapter

- `src/dcc_mcp_photoshop/install_service.py::apply_install` stages the bridge,
  writes a redacted receipt, and calls `verify_photoshop_rpc`. When no trusted
  session exists it returns `requires_restart` with
  `bounded_photoshop_uxp_bootstrap_unavailable` and an empty `next_steps`. It
  never calls the bootstrap handshake, so the installer cannot use a plugin that
  loaded at host startup to establish the session by itself.
- `src/dcc_mcp_photoshop/photoshop_bootstrap.py` already drives the adobepy
  0.12.0 two-step, identity-bound handshake
  (`bootstrap_photoshop_uxp` / `verify_photoshop_bootstrap`, `require_request`
  / `require_continuation`, same-runtime-instance binding) over an injected
  `BrokerClient`, and is fully offline-testable. The upstream feature request
  (`adobepy#67`) is closed and the API is released; the missing piece is
  adapter-side integration, not an upstream dependency.
- `skills/photoshop-setup/scripts/setup_uxp_plugin.py` redirects every legacy
  setup call to the canonical `install` lifecycle. Adobe owns plugin
  registration and loading, so the adapter currently has no plugin-link /
  auto-load step equivalent to the sibling adapters' debug-link path.
- `pyoxidizer.bzl` already builds a standalone single-file binary (no Python
  runtime for end users), but `pyproject.toml` still declares `adobepy`,
  `dcc-mcp-core`, and `websockets` as runtime dependencies for the wheel path,
  and releases contain no `.ccx` artifact. The UXP bridge template belongs to
  the separately released adobepy project.
- `install.md` documents the current trusted-session blocker honestly. Its
  `dependency_issue` points at a closed upstream item, which is misleading and
  should be replaced with the real adapter-side precondition.

## Staged plan

Each item is a separate, review-gated change. Items 1 and 4 are fully
offline-verifiable; items 2 and 3 have host-gated parts that cannot be accepted
from offline tests alone.

1. **Default to the standalone binary.** Make the PyOxidizer single-file build
   the documented default install. Keep the wheel as the development/fallback
   path. The end-user contract becomes "one binary, no Python runtime, no
   separately installed third-party packages". Anchor: `pyoxidizer.bzl`,
   `pyproject.toml`, `docs/distribution.md`, `install.md`.

2. **Bundle the approved runtime pieces.** Ship the checksum-verified adobepy
   Windows CLI, the UXP bridge template, and broker lifecycle management in one
   install package; manage `ADOBEPY_TOKEN`, broker start/stop, and
   `ADOBEPY_BROKER_URL` internally instead of asking the operator to download,
   verify, and wire them by hand. Anchors: `install_contract.py`
   (`_ADOBEPY_CLI_RELEASES`-style checksum table), `install_planning.py`
   (`build_install_report`), `install_discovery.py`. The exact-release checksum
   verification stays; it is a supply-chain control, not a user burden.

3. **One-time plugin registration and auto-load.** Add an idempotent plugin-link
   / registration step equivalent to the sibling adapters' debug-link path, so
   the bridge loads at Photoshop startup rather than through a manual UXP
   Developer Tools "Load Plugin" action. Anchors:
   `skills/photoshop-setup/scripts/setup_uxp_plugin.py`, a new setup-plan
   helper, and the install lifecycle's `next_steps`. Plugin registration stays a
   host-side fact; the adapter records it but does not fabricate it.

4. **Wire the bounded bootstrap into the install lifecycle.** When real host,
   plugin, and receipt facts are available, `apply_install` attempts the
   two-step handshake through `photoshop_bootstrap.bootstrap_from_facts` before
   falling back to the honest blocker. Assemble facts only from the receipt, the
   observed process identity, and the broker; never invent them. Anchors:
   `install_service.py`, `photoshop_bootstrap.py`, `install_verification.py`.

## Host provenance vs. runtime identity

Two different checks are often conflated:

- **Install-time host provenance (A).** Authenticode status plus host product
  metadata, used to decide whether a discovered `Photoshop.exe` is plausible.
  A repackaged host can produce a `HashMismatch` status while still carrying
  genuine Adobe signer, company, product, and version metadata. The proposed
  default is warn-and-proceed with a recorded warning for that specific case,
  keeping unsigned, non-Adobe-signer, and foreign-product hosts fatal. Because
  a hash mismatch cannot by itself distinguish a repack from a forged signature
  blob, this relaxation is an explicit, auditable policy decision that must be
  reviewed independently before release; it is not bundled into an unrelated
  change. Anchors: `install_discovery.py` (`_windows_signature_label`,
  `attest_photoshop_executable`), `install_planning.py`
  (`_host_provenance_warnings`), `cli.py` (`--allow-unverified-host`).
- **Runtime exact-instance identity (B).** Executable hash, host version, PID,
  process start identity, and instance id bound to one broker session. adobepy
  0.12.0 requires these for a trusted UXP session, so they cannot be deleted.
  The installer should collect them internally so the operator never supplies
  them, and `verify_photoshop_rpc` keeps enforcing them. Anchor:
  `install_verification.py`, `photoshop_bootstrap.py`.

**Never** bypass broker identity, fabricate a session, weaken Windows trust
policy, add a COM/GUI fallback as the default path, or start an executable that
failed provenance checks.

## Verification boundaries

Offline-verifiable: unit and contract tests for staging, receipts, rollback,
report shape, the bootstrap handshake over an injected client, host provenance
classification, and plugin setup-plan generation. The full suite passes in an
isolated environment with the pinned SDK (`adobepy==0.12.0`) and this checkout
installed editable.

Not offline-verifiable: a real trusted UXP session, native gateway discovery,
and any native end-to-end host call. These require a normally signed, startable
Photoshop with the bridge plugin actually loaded. No offline test may be
reported as native acceptance; the report must stay `requires_restart` with an
honest blocker until the broker grants the session.

## First code increment (separate change)

The first implementation change is item 4 in its smallest safe form: an
additive lifecycle path that attempts the bounded handshake only when all
required facts are present and a broker client is reachable, and otherwise
returns the existing blocker unchanged. Its tests must cover: a successful
handshake over a fake `BrokerClient`, an identity mismatch, a missing-facts
fallback, and a broker-unavailable fallback. The install report contract,
existing `next_steps` assertions, and all security invariants stay unchanged in
that increment.
