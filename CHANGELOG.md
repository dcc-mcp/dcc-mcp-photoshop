# Changelog

## [0.1.8](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.7...v0.1.8) (2026-06-09)


### Bug Fixes

* correct skill count and remove broken references in README ([4eb55d3](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4eb55d3c7c8d6c4317bf2dfcaae96b2c40417441))


### Documentation

* update README with comprehensive MCP installation and configuration guide ([0e2aebb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0e2aebbcfea2b663377c188bd1e52b7ac49c022c))

## [0.1.7](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.6...v0.1.7) (2026-06-09)


### Features

* define Photoshop UXP WebSocket bridge protocol v0.1.0 ([f7bc2cc](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/f7bc2cc37b79f5cb65c6b204391f1a0ebed9d338))


### Bug Fixes

* apply ruff formatting to conftest.py and test_protocol.py ([571bdb7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/571bdb761ede201661720b6856bc3e344ce4c8de))
* resolve ruff lint errors (F401, I001, B904) ([de6cd2b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/de6cd2b37b24edf87857cbd6018de5ccea6bc065))

## [0.1.6](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.5...v0.1.6) (2026-06-08)


### Code Refactoring

* migrate PhotoshopMcpServer to extend DccServerBase (4-seam controller PIP-688) ([6081dbd](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6081dbda37ae47162729899f617fbde07730c385))

## [0.1.5](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.4...v0.1.5) (2026-06-08)


### Bug Fixes

* adapt DccServerBase to core v0.18.14 DccServerOptions API ([dfd5b6f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dfd5b6fd76c835ef3fbee4478129c220ac25a0c6))

## [0.1.4](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.3...v0.1.4) (2026-06-07)


### Bug Fixes

* apply ruff format to test_agent_instruction_files.py ([e466dd0](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e466dd0dd31abb07a4ea18437a538d0168b5b723))
* ruff import organization in test_agent_instruction_files.py ([c695bb9](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c695bb97b23f7a529d140131b04895dc9aa7da01))

## [0.1.3](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.2...v0.1.3) (2026-06-06)


### Bug Fixes

* **ci:** isolate workflow_dispatch from push concurrency in release workflow ([#12](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/12)) ([7896fa8](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7896fa8631117f929b27d543963d6162af210706))

## [0.1.2](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.1...v0.1.2) (2026-06-06)


### Features

* migrate skills to adobepy facade ([#10](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/10)) ([6470ca8](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6470ca8b975019c0b59c2a4a2eaf4d3cd61cebac))

## [0.1.1](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.0...v0.1.1) (2026-06-05)


### Features

* add photoshop-layers/image/text skills, exponential back-off reconnect, persistent log ([b2f4ef5](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b2f4ef5c1a849a9c9df1630921061d28de360c9f))
* create GitHub repo with CI/CD, bump dcc-mcp-core to &gt;=0.12.29, clean up server.py fallback code ([b85309e](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b85309e64c562cbf5b8f1ec39507a91995d6097a))
* implement Photoshop MCP adapter with UXP WebSocket bridge ([d67b144](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d67b144d3c5c98c7e63563ac60b6eb09cdf52bc1))
* initial placeholder for dcc-mcp-photoshop ([73542e5](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/73542e5eb84a5687e8475c4fe1684b800b9e5d2f))
* upgrade to dcc-mcp-core 0.12.23 gateway mode with progressive skill loading ([a197c79](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a197c79342eac4b604b49389ae9131c53b14c92c))


### Bug Fixes

* correct lint_skills.py path resolution (scripts/scripts double nesting), update cli.py ([74e34b2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/74e34b2b2598a65fa652cf9bff65bc35f7da2951))
* use concurrent.futures.TimeoutError for cross-version compat ([49d2c32](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/49d2c320dc943cff1c497fe45b5078cd8fba4852))
