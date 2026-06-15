# Changelog

## [0.1.17](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.16...v0.1.17) (2026-06-15)


### Documentation

* add agent-facing docs and fix stale references ([22a810a](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/22a810a66279f9e3865d928a16beaa651a349f62))

## [0.1.16](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.15...v0.1.16) (2026-06-10)


### Features

* switch packaging from PyInstaller to PyOxidizer ([6bd1867](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6bd186713247fdca78be63d489e61025fd7e00f1))

## [0.1.15](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.14...v0.1.15) (2026-06-09)


### Features

* add bilingual README (readme.md / readme_zh.md) following standard template ([337c0d8](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/337c0d8350cbb85a68cba8f73cf9e639987e4ae1))


### Bug Fixes

* apply ruff format to bridge.py to fix CI lint ([84c0d98](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/84c0d98f8eb8f8445bb03ea9a687989ecb5d1b9f))
* correct release-please README path to uppercase README.md ([e8cdd2c](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e8cdd2c9d72c4269aa2741f2330bd853bcda2be3))
* implement BridgeRpcServer, add _posix_sidecar_launcher and pack lint ([3dc3df2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/3dc3df2e4b317e8fde719d02890231a3b27b8c34))
* remove hardcoded version URLs, add README to release-please extra-files ([4ddc5b2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4ddc5b24e77a6fc516fc1e1cf695ef7091a84ab4))
* remove pip install step from Quick Start — everything is bundled in .ccx ([c9f15ba](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c9f15bad7a786201b9e31a89b57f0c211d135244))
* remove pip install step from Quick Start — everything is bundled in .ccx ([a5a2992](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a5a2992a86f29f9ae6d1926eec73f76f51b691cd))
* remove unused socketserver import, restore missing _update_manifest_version ([d8f5e85](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d8f5e85c98118bbe7419010aa75b5961d86252b3))
* use uppercase README filenames and unify MCP config to gateway URL ([86828b3](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/86828b3beadb5b0f70692bb8931b6f7d59ddae13))

## [0.1.14](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.13...v0.1.14) (2026-06-09)


### Bug Fixes

* restore _hidden_vbs_launcher, _sidecar_launcher, _sidecar_stopper to pack_plugin.py ([c29b2ef](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c29b2ef351fc5000e211351cec7f8324dea9ca08))
* restore sidecar helper functions to pack_plugin.py ([9d391a0](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9d391a0b5ec99826b98f3333d85a449567746fec))

## [0.1.13](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.12...v0.1.13) (2026-06-09)


### Features

* add configure_mcp_client tool to photoshop-setup skill ([83a8544](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/83a8544ca6f17f063a6ee08cfabaee8b0457a707))
* add pre-commit hooks and vx.toml for vx prek workflow ([dd385a8](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dd385a81a1a51340b1dc923a7d3aeda31af10518))


### Bug Fixes

* add missing _write_bridge_url_to_config and _remove_bridge_config to api.py ([7d07ca4](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7d07ca410e0d1f4f6db4d09c4cb772de699001cc))
* remove unused pathlib.Path import to pass ruff F401 lint ([b1a4284](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b1a428423c3d86b2f70a4607bcdcf7b246a2e774))
* run ruff format on configure_mcp_client.py to pass CI lint ([684a70d](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/684a70d0ccc766ef8175cd69e7c6a5697a37bfc7))


### Documentation

* add bilingual quick-start to README with plugin install and gateway config ([81ff0fb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/81ff0fbbc4baaa9815cfdfd277d9ba6594392fd4))
* unify gateway URL to /mcp endpoint in README ([5129d66](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/5129d664f737b8e2191548ec8446c485ec070c4e))

## [0.1.12](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.11...v0.1.12) (2026-06-09)


### Bug Fixes

* restrict release workflow builds to tag push only ([e77c195](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e77c1954b2782e3cc5b8f3310fdfa19196924363))

## [0.1.11](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.10...v0.1.11) (2026-06-09)


### Bug Fixes

* add missing _hidden_vbs_launcher, _sidecar_launcher, _sidecar_stopper to pack_plugin.py ([4d555b1](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4d555b174c85ffa63f1098d3e8bd5d0d8ea422d9))
* add sidecar download and staging steps to CI build-uxp-plugin job ([e821488](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e8214884a08bd3cb0853794d8daf30d508ec3d0b))

## [0.1.10](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.9...v0.1.10) (2026-06-09)


### Features

* download dcc-mcp-server from dcc-mcp-core releases instead of committing binary ([1acdda7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/1acdda79b9c009732c10b7bfc11d2157f6aae1eb))


### Bug Fixes

* add missing BRIDGE_URL_ENV_VAR constant to api module ([19f553e](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/19f553eb1af7d9526a555c3db89b5d9ab9a61438))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([19f553e](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/19f553eb1af7d9526a555c3db89b5d9ab9a61438))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([632ef30](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/632ef309d4fee65f48a5a544a585bad17f01fa24))

## [0.1.9](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.8...v0.1.9) (2026-06-09)


### Features

* create photoshop-setup skill for agent-guided MCP setup ([#26](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/26)) ([cd22358](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/cd2235846329d43756a70dcb4e5537c6ec89f8c5))

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
