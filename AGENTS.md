# AGENTS.md — dcc-mcp-photoshop

> **Navigation map, not a reference manual.**
> Follow the links; don't read everything upfront.
> **This file is the only agent contract file at the repository root** — see
> [Agent Contract Files](#agent-contract-files).

## Agent Control Path

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

## Project Overview

**dcc-mcp-photoshop** turns Adobe Photoshop into an MCP Streamable HTTP backend via a UXP WebSocket plugin. The Python bridge runs a WebSocket server on port 9001; the UXP plugin inside Photoshop connects as a client.

## Agent Entry Path

```
AI Agent
  │  MCP Streamable HTTP → http://127.0.0.1:9765/mcp
  ▼
dcc-mcp-server Gateway (auto-discovers DCC via capability index)
  │
  ▼
PhotoshopMcpServer [Python sidecar]
  │  WebSocket JSON-RPC (port 9001)
  ▼
UXP Plugin [JavaScript, runs inside Photoshop]
  │  UXP API calls
  ▼
Adobe Photoshop 2022+
```

## Entry Strategy

| Scenario | Path |
|----------|------|
| AI agent / CLI runtime | `dcc-mcp` + `dcc-mcp-cli` over gateway REST `/v1/search`, `/v1/describe`, and `/v1/call` |
| IDE user (Cursor, Claude Desktop) | Configure `mcpServers` → `url: "http://127.0.0.1:9765/mcp"` |
| Development / debugging | Embedded mode: `dcc-mcp-photoshop --embedded` (MCP server + bridge in one process) |

## Skills-First Workflow

When using Photoshop through dcc-mcp-photoshop, prefer skills over raw scripting:

```
1. SEARCH: search_skills(query="photoshop") → find available skill packages
2. CHECK: Read the skill's SKILL.md description and tools
3. LOAD:   load_skill("photoshop-document") → expose the tools
4. CALL:   Call the specific tool with validated parameters
5. FOLLOW UP: Check structured results for next steps
```

### Available Skills

| Skill | Tools | Purpose |
|-------|-------|---------|
| `photoshop-setup` | 6 | Install, configure, verify bridge connection |
| `photoshop-document` | 2 | Document info, list layers |
| `photoshop-image` | 7 | Create document, export, resize, flatten, merge |
| `photoshop-layers` | 8 | Layer CRUD, opacity, visibility, blend mode, fill |
| `photoshop-text` | 3 | Create, update, inspect text layers |

## CLI Modes

| Mode | Command | Use Case |
|------|---------|----------|
| Bridge-only (default) | `dcc-mcp-photoshop` | Deployment with external `dcc-mcp-server` |
| Embedded | `dcc-mcp-photoshop --embedded` | Development (MCP + bridge in one process) |
| Daemon | `dcc-mcp-photoshop --daemon` | Non-interactive background startup |

## Distribution Channels

| Channel | Artifact | Python Required |
|---------|----------|-----------------|
| PyPI | `dcc-mcp-photoshop` wheel + sdist | Yes (3.8+) |
| GitHub Release | Standalone binary (Win/Linux/Mac) | No |
| GitHub Release | UXP `.ccx` plugin | No |

## Agent Contract Files

`AGENTS.md` is the **only** agent contract file at the repository root. It is the
native instruction file for Codex, OpenCode, Cursor, GitHub Copilot, Windsurf,
Cline, Roo Code, Kiro, Trae, and Augment, and Claude Code falls back to it when
no `CLAUDE.md` exists. Guidance that used to live in `CLAUDE.md` has been folded
into [**Agent Workflow**](#agent-workflow) below.



---

## Agent Workflow

`CLAUDE.md` was a thin shim that only redirected to this file. Its content
lives here now.

**Read order.**

1. `AGENTS.md` (this file) — navigation map, available skills, response rules.
2. `llms.txt` — compact API index with all tools and CLI options.
3. `docs/bridge-protocol.md` — WebSocket JSON-RPC protocol between the Python bridge and the UXP plugin.
4. `docs/distribution.md` — distribution channels and release workflow.

**Mandatory DCC workflow.** Drive Photoshop through the Skills-First workflow
described above — never through raw subprocess or Adobe CLI calls:

1. `search_skills("photoshop")` → find available skills.
2. `load_skill("photoshop-<name>")` → load the skill.
3. Call the specific tool with validated parameters.

**Build and test** — always go through `vx just`; do not call `uv` or `pytest`
directly.

| Task | Command |
|------|---------|
| Install (editable) | `vx just dev` |
| Run tests | `vx just test` |
| Tests with coverage | `vx just test-cov` |
| Lint | `vx just lint` |
| Format | `vx just format` |
| Lint everything | `vx just lint-all` |
| Full CI locally | `vx just ci` |

---

## ## Key Files

| File | Purpose |
|------|---------|
| `README.md` | Human-readable project documentation (EN) |
| `README_zh.md` | Human-readable project documentation (ZH) |
| `CHANGELOG.md` | Release history |
| `docs/PRD.md` | Product Requirements Document |
| `docs/bridge-protocol.md` | WebSocket JSON-RPC 2.0 bridge protocol spec |
| `docs/distribution.md` | Distribution & release guide |
| `src/dcc_mcp_photoshop/` | Python package source |
| `bridge/uxp-plugin/` | UXP plugin (JavaScript, runs inside Photoshop) |

## Response Language

- Reply to the user in **Simplified Chinese** by default.
- Keep all code, identifiers, commit messages, and file contents in **English**.

## PR / Commit Rules

- No AI-attribution footers in PR bodies or commit messages.
- Rebase onto main before merging — no merge commits.
- CI must pass before review.
