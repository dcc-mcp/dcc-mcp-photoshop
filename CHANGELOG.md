# Changelog

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
