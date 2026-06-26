# CLAUDE.md — dcc-mcp-photoshop

> Entry point for Anthropic Claude agents.
> This file intentionally delegates to `AGENTS.md` so project rules stay single-sourced.
> Do not copy detailed project guidance here — update `AGENTS.md` or `llms.txt` instead.

## Read Order

1. `AGENTS.md` — navigation map, available skills, and response rules.
2. `llms.txt` — compact API index with all tools and CLI options.
3. `docs/bridge-protocol.md` — WebSocket JSON-RPC protocol between Python bridge and UXP plugin.
4. `docs/distribution.md` — distribution channels, release workflow.

## Mandatory DCC Workflow

When interacting with Adobe Photoshop through dcc-mcp-photoshop, use the Skills-First workflow described in `AGENTS.md`:
1. `search_skills("photoshop")` → find available skills
2. `load_skill("photoshop-<name>")` → load the skill
3. Call the specific tool with validated parameters

Do not use raw subprocess or adobe CLI calls.

## Build & Test

```bash
# Install (editable)
uv pip install -e .

# Run tests
uv run pytest

# Format + lint
uv run ruff format .
uv run ruff check .
```
