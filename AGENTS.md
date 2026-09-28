# AGENTS.md — dcc-mcp-photoshop

> Adobe Photoshop adapter for the DCC Model Context Protocol. MCP tools reach
> Photoshop through a Python sidecar and a UXP WebSocket bridge.
> Navigation map for AI agents, not a reference manual. Follow the links; do not
> read everything up front.

## Build & test

```bash
vx just dev        # install the package in editable mode with dev extras
vx just test       # run the pytest suite
vx just ci         # everything CI runs: test + lint + lint-format + lint-skills
```

Other verified recipes — run `vx just` to list all: `lint`, `lint-format`,
`lint-skills`, `fix`, `format`, `test-cov`, `build` (wheel + sdist),
`build-binary` (standalone binary), `clean`, `check-release-workflow`.

## Read order

1. `AGENTS.md` — this navigation map.
2. `llms.txt` — compact runtime chain, CLI options, failure modes.
3. `docs/bridge-protocol.md` — WebSocket JSON-RPC protocol, Python bridge ↔ UXP plugin.
4. `docs/distribution.md` — distribution channels and release workflow.

## Agent control path

AI agent runtimes default to the shared gateway through the
`dcc-mcp` skill and `dcc-mcp-cli` REST commands:

```bash
dcc-mcp-cli search --query "<task>" --dcc-type photoshop
dcc-mcp-cli describe <tool-slug>
dcc-mcp-cli call <tool-slug> --json '{"key":"value"}'
```

Use `dcc-mcp-cli list` for live instances and `dcc-mcp-cli dcc-types` for
release-catalog support. IDE users may continue to configure the gateway MCP
endpoint; adapter-local Python start APIs are for host bootstrap and tests.

### CLI availability and updates

If `dcc-mcp-cli` is missing, obtain user consent before using the official
install commands in the README Agent workflow. Keep an official build current
with:

```bash
dcc-mcp-cli update check
dcc-mcp-cli update apply
```

`update apply` stages the latest CLI for the next launch; it does not replace
a running server.

## Runtime chain

```
AI agent
  │  MCP Streamable HTTP → http://127.0.0.1:9765/mcp
  ▼
dcc-mcp-server gateway (auto-discovers the DCC via capability index)
  │
  ▼
PhotoshopMcpServer [Python sidecar]
  │  skill scripts → adobe.photoshop.Photoshop() → BrokerClient
  │  HTTP JSON-RPC → http://127.0.0.1:47391  (`ADOBEPY_BROKER_URL`)
  ▼
adobepy broker [Rust]
  │  WebSocket JSON-RPC
  ▼
adobepy UXP bridge [JavaScript, runs inside Photoshop]
  │  UXP API calls
  ▼
Adobe Photoshop 2022+
```

The UXP bridge is **generated, not vendored**: `adobepy install-bridge photoshop
--dest <dir>` writes it (see `llms.txt` and `install.md`). There is no
`bridge/` directory in this repository.

## Entry strategy

| Scenario | Path |
|---|---|
| AI agent / CLI runtime | `dcc-mcp` + `dcc-mcp-cli` over gateway REST `/v1/search`, `/v1/describe`, `/v1/call` |
| IDE user (Cursor, Claude Desktop) | Configure `mcpServers` → `url: "http://127.0.0.1:9765/mcp"` |
| Development / debugging | Embedded mode: `dcc-mcp-photoshop --embedded` (MCP server + bridge in one process) |

## Skills-first workflow

Prefer skills over raw scripting:

```
1. SEARCH:  search_skills(query="photoshop") → find available skill packages
2. CHECK:   read the skill's SKILL.md description and tools
3. LOAD:    load_skill("photoshop-document") → expose the tools
4. CALL:    call the specific tool with validated parameters
5. FOLLOW:  check the structured result for next steps
```
| Skill | Tools | Purpose |
|---|---|---|
| `photoshop-setup` | 6 | Install, configure, verify bridge connection |
| `photoshop-document` | 2 | Document info, list layers |
| `photoshop-image` | 7 | Create document, export, resize, flatten, merge |
| `photoshop-layers` | 8 | Layer CRUD, opacity, visibility, blend mode, fill |
| `photoshop-text` | 3 | Create, update, inspect text layers |

Fall back to raw scripting only when no typed skill fits.

## CLI modes

| Mode | Command | Use case |
|---|---|---|
| Bridge-only (default) | `dcc-mcp-photoshop` | Deployment with an external `dcc-mcp-server` |
| Embedded | `dcc-mcp-photoshop --embedded` | Development (MCP + bridge in one process) |
| Daemon | `dcc-mcp-photoshop --daemon` | Non-interactive background startup |

Requires Python `>=3.8`; the standalone binary and the UXP bridge need no Python.

## Repo layout

| Path | Role |
|---|---|
| `src/dcc_mcp_photoshop/` | Python adapter package — server, bridge client, install lifecycle, CLI |
| `tests/` | pytest suite, including contract tests for skills and release workflow |
| `docs/` | `bridge-protocol.md`, `distribution.md`, `PRD.md` |
| `tools/` | `build_binary.py`, `lint_skills.py`, `download_dcc_mcp_server.py` |
| `scripts/ci/` | CI support, e.g. the release-workflow digest check |
| `llms.txt` | Compact agent entry point (runtime chain, install, failure modes) |
| `justfile` | Task runner; list recipes with `vx just` |

## Release

- release-please drives versioning from Conventional Commits on `main`.
- Whether a release is cut at all is a changelog question, not a prefix question: if every
  commit in the batch lands in a `hidden: true` section the changelog entry is empty, and
  release-please skips the whole batch — no release pull request, **no version bump**
  (`strategies/base.ts` logs “No user facing commits found since … - skipping” when
  `changelogEmpty()` finds only the heading line).
- This repo overrides `changelog-sections` in `release-please-config.json`: `feat:`, `fix:`, 
  `perf:`, `refactor:` and `docs:` are **visible**; `style:`, `chore:`, `test:`, `ci:` and
  `build:` are `hidden: true`. A visible `refactor:` therefore cuts a release.
- Only once a release *is* cut does the prefix choose the bump. This repo is pre-1.0 and sets
  `bump-minor-pre-major` and `bump-patch-for-minor-pre-major`, so on `0.x`: breaking → minor
  and `feat:` → **patch** — not major/minor. Anything else → patch.
- Use `chore:` when the batch should **not** cut a release; use `docs:` when doc-only work
  should cut a patch release.
- Version is mirrored into `pyproject.toml`, `src/dcc_mcp_photoshop/__version__.py`,
  `README.md`, and `README_zh.md`; do not edit those by hand.

## Response language

- Reply to the user in **Simplified Chinese** by default.
- Keep code, identifiers, commit messages, and file contents in **English**.

## Do / Don't

- **Do** single-source agent instructions here — this is the only agent contract
  file at the repo root. Rebase onto `main` before merging (no merge commits);
  CI must pass before review.
- **Don't** add `CLAUDE.md` / `GEMINI.md` / `CURSOR.md` / `ANTHROPIC.md` /
  `OPENAI.md` / `COPILOT.md` / `CODEBUDDY.md` / `.cursorrules` / `.clinerules` /
  `.windsurfrules` at the root. This repo has no `docs/integrations/`; keep any
  vendor-specific notes here.
- **Don't** hardcode an exact version in tests (`assert __version__ == "X.Y.Z"`)
  — release-please bumps will break it. Use `>=` or read package metadata.
- **Don't** commit build artifacts to the repo root (`dist/`, `build/`,
  `coverage.json`, `*.egg-info`); `vx just clean` removes them.
- **Don't** add AI-attribution footers to PR bodies or commit messages.
