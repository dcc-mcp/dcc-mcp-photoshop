# Changelog

## [0.1.28](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.27...v0.1.28) (2026-07-13)


### Bug Fixes

* restore typed Photoshop skill execution ([#77](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/77)) ([a7868f5](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a7868f51105c19ffd260ef0386ad5a01aacb0739))

## [0.1.27](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.26...v0.1.27) (2026-07-13)


### Bug Fixes

* align Photoshop setup with adobepy ([#76](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/76)) ([a69a923](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a69a9230d8e8cf8b1fa22bad559a2b8c2cf8cab2))
* bundle current dcc-mcp core train ([4d99076](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4d99076aa997c2f5d30f7979ab6da9fdc7e6cf39))

## [0.1.26](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.25...v0.1.26) (2026-07-05)


### Bug Fixes

* bump dcc-mcp-core to &gt;=0.19.8 and avoid config name collision ([db5390b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/db5390ba51fd4382304326120c099f536076f5c2))

## [0.1.25](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.24...v0.1.25) (2026-06-27)


### Features

* add photoshop-layers/image/text skills, exponential back-off reconnect, persistent log ([5c6eea3](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/5c6eea3fe4a1f1b593be7cdd95b28fd845605dd7))
* create GitHub repo with CI/CD, bump dcc-mcp-core to &gt;=0.12.29, clean up server.py fallback code ([3f9e69a](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/3f9e69afdb94e9280a62b45a7f25ec2d1ef3c3fd))
* create photoshop-setup skill for agent-guided MCP setup ([b1a9a96](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b1a9a9640e0e02d2b6a50c577605173ce102ccd4))
* create photoshop-setup skill for agent-guided MCP setup ([#26](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/26)) ([7851d61](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7851d61c051b70c83d6a332627fc876c59d8d93b))
* define Photoshop UXP WebSocket bridge protocol v0.1.0 ([6e6fb2b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6e6fb2bc2bb3805038d460257df4d18be713ddb2))
* define Photoshop UXP WebSocket bridge protocol v0.1.0 ([6799ebe](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6799ebee17ad2e9f38f9b7b92df8e11445eb9b09))
* download dcc-mcp-server from dcc-mcp-core releases instead of committing binary ([0db0d53](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0db0d53806c358490f538b53075fa4c93e7adef0))
* implement Photoshop MCP adapter with UXP WebSocket bridge ([bef0f78](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/bef0f782467f4071d6131285b15b5bee9ec27313))
* initial placeholder for dcc-mcp-photoshop ([83b5d80](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/83b5d80a8206ec838a5d652ead55c4da234e8a26))
* migrate skills to adobepy facade ([#10](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/10)) ([6704c18](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6704c1841f43020fe9f5188664b8497c68537bc8))
* upgrade to dcc-mcp-core 0.12.23 gateway mode with progressive skill loading ([1df9736](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/1df97365ddd205aa90b4390151840693f7c5f3fb))


### Bug Fixes

* adapt DccServerBase to core v0.18.14 DccServerOptions API ([9dd79ff](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9dd79ffab6566103d9986d1fbf1090a7316be6e0))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([197e069](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/197e0696f4c71e71da2d0c3124077b6927f0f3b0))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([197e069](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/197e0696f4c71e71da2d0c3124077b6927f0f3b0))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([b0aae72](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b0aae72f1b3ab409ab2fe15660e7730f4da6c8e2))
* apply ruff format to test_agent_instruction_files.py ([a233860](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a2338605d1e6852dbbc421293e84fca34a415c90))
* apply ruff formatting to conftest.py and test_protocol.py ([dccc761](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dccc76167b29b567833e93de7cade96a7accfa1e))
* apply ruff formatting to conftest.py and test_protocol.py ([6ed1a5f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6ed1a5f0d3d406d5b66f7cad800d314f8a1ecc47))
* **ci:** isolate workflow_dispatch from push concurrency in release workflow ([#12](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/12)) ([b482f06](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b482f065a0092f6b74eb3eb9842f98e826061dc2))
* correct lint_skills.py path resolution (scripts/scripts double nesting), update cli.py ([958fb14](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/958fb148a476d9c45d746e5842022434e6a37eaa))
* correct skill count and remove broken references in README ([dbb7e83](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dbb7e832c26c61ba9bb5610530710a5926672408))
* recover main from v0.1.24 ([58a4a29](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/58a4a29b3d144b9f173c561b289d273482eff462))
* replace hardcoded version assertion with dynamic semver check ([a40ccf5](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a40ccf5d8da93b81120bf94266c9c242bc59a63e))
* resolve ruff lint and format issues in photoshop-setup scripts ([43684df](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/43684dfcc204e14803173165ab0faf95b6335e03))
* resolve ruff lint errors (F401, I001, B904) ([262d43f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/262d43fb6c6534c60b7e08cf5b26de8e437aaeeb))
* resolve ruff lint errors (F401, I001, B904) ([74da278](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/74da278bfd1a2c180e15b7584a1f4b62b0b6abc5))
* ruff import organization in test_agent_instruction_files.py ([578fb45](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/578fb454c173fa699fcf928478a8e1321ff4b479))
* use concurrent.futures.TimeoutError for cross-version compat ([07bbae4](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/07bbae4144d81d79a93519c8f5c38d2cd181cac8))


### Code Refactoring

* migrate PhotoshopMcpServer to extend DccServerBase (4-seam controller PIP-688) ([c36f85f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c36f85ff33a8d20d5adf3a44bb73a2c3feb11cda))


### Documentation

* update README with comprehensive MCP installation and configuration guide ([e7e5dd0](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e7e5dd06ef230d9c43592fefb931655803d80cea))

## [0.1.24](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.23...v0.1.24) (2026-06-23)


### Features

* add bilingual README (readme.md / readme_zh.md) following standard template ([3d6d0e2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/3d6d0e2e3779ecdeea78d739689a46db20c5be8f))
* add configure_mcp_client tool to photoshop-setup skill ([f836cc4](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/f836cc43a0aab96b4c51fd1f6c538e7ba51d548c))
* add configure_mcp_client tool to photoshop-setup skill ([992a817](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/992a8179a51637322b0e18accafe799dcf5c15e4))
* add daemon-first startup, failure state tracking, and bridge version validation ([38f0eb6](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/38f0eb64a43361e27780d916abe2e329f8315d69))
* add install_photoshop_connector.ps1 one-click installer + smoke check ([9df6aa7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9df6aa76ef8f81e2882a47dc9a43e06381bfc220))
* add photoshop-layers/image/text skills, exponential back-off reconnect, persistent log ([5c6eea3](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/5c6eea3fe4a1f1b593be7cdd95b28fd845605dd7))
* add pre-commit hooks and vx.toml for vx prek workflow ([4d205c6](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4d205c6ac558a90ff8cd38dd6ef4679078545a57))
* add pre-commit hooks and vx.toml for vx prek workflow ([20586c9](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/20586c9c7d7cb6a1319a709b41ddb7e91df30bfa))
* add upgrade/uninstall/rollback/version-check to install script ([0554dca](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0554dca4b053dcdcee813a6e5f7da91acff3c1cd))
* create GitHub repo with CI/CD, bump dcc-mcp-core to &gt;=0.12.29, clean up server.py fallback code ([3f9e69a](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/3f9e69afdb94e9280a62b45a7f25ec2d1ef3c3fd))
* create photoshop-setup skill for agent-guided MCP setup ([b1a9a96](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b1a9a9640e0e02d2b6a50c577605173ce102ccd4))
* create photoshop-setup skill for agent-guided MCP setup ([#26](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/26)) ([7851d61](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7851d61c051b70c83d6a332627fc876c59d8d93b))
* define Photoshop UXP WebSocket bridge protocol v0.1.0 ([6e6fb2b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6e6fb2bc2bb3805038d460257df4d18be713ddb2))
* define Photoshop UXP WebSocket bridge protocol v0.1.0 ([6799ebe](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6799ebee17ad2e9f38f9b7b92df8e11445eb9b09))
* download dcc-mcp-server from dcc-mcp-core releases instead of committing binary ([0db0d53](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0db0d53806c358490f538b53075fa4c93e7adef0))
* gateway daemon-first startup, failure tracking, bridge version validation ([0f012e2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0f012e2c1c29ea97da5700cf5ad7a9622d1070df))
* gateway daemon-first startup, failure tracking, bridge version validation ([#44](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/44)) ([0f012e2](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0f012e2c1c29ea97da5700cf5ad7a9622d1070df))
* implement Photoshop MCP adapter with UXP WebSocket bridge ([bef0f78](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/bef0f782467f4071d6131285b15b5bee9ec27313))
* initial placeholder for dcc-mcp-photoshop ([83b5d80](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/83b5d80a8206ec838a5d652ead55c4da234e8a26))
* install_photoshop_connector.ps1 one-click installer + smoke check ([4b144fc](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4b144fc79d9abd9049b8442a788a3241cb2efa49))
* migrate skills to adobepy facade ([#10](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/10)) ([6704c18](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6704c1841f43020fe9f5188664b8497c68537bc8))
* PIP-673 adapter capabilities and code convergence ([74cd493](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/74cd4938315d3bb3fb0ee1697b27da47505e2fc4))
* stability improvements toward Maya parity (PIP-1775) ([d562120](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d56212016522b5b05e8eb0200ca0ff2c638d724e))
* stability improvements toward Maya parity (PIP-1775) ([fa0dfd8](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/fa0dfd8086ca97a391be8aa47cdc005524a51173))
* stability improvements toward Maya parity (PIP-1775) ([#60](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/60)) ([d562120](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d56212016522b5b05e8eb0200ca0ff2c638d724e))
* switch packaging from PyInstaller to PyOxidizer ([f0a7f63](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/f0a7f631561f2528a447770ddd2fec43ca118c9f))
* upgrade to dcc-mcp-core 0.12.23 gateway mode with progressive skill loading ([1df9736](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/1df97365ddd205aa90b4390151840693f7c5f3fb))


### Bug Fixes

* adapt DccServerBase to core v0.18.14 DccServerOptions API ([9dd79ff](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9dd79ffab6566103d9986d1fbf1090a7316be6e0))
* add missing _hidden_vbs_launcher, _sidecar_launcher, _sidecar_stopper to pack_plugin.py ([12429fb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/12429fbffbb806057bd610771ee9358f11b43740))
* add missing _write_bridge_url_to_config and _remove_bridge_config to api.py ([9ac1582](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9ac1582867ceff55ab636e6f13808617dbe85f27))
* add missing _write_bridge_url_to_config and _remove_bridge_config to api.py ([e3b83a7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e3b83a72cedf3c633696fc5f1e01248005cc5713))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([197e069](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/197e0696f4c71e71da2d0c3124077b6927f0f3b0))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([197e069](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/197e0696f4c71e71da2d0c3124077b6927f0f3b0))
* add missing BRIDGE_URL_ENV_VAR constant to api module ([b0aae72](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b0aae72f1b3ab409ab2fe15660e7730f4da6c8e2))
* add pyoxidizer installation in release build-binary job ([e743b0d](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e743b0de88f6f297502681019538be83131113f9))
* add sidecar download and staging steps to CI build-uxp-plugin job ([31bfd19](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/31bfd197d1352f5413445c1d70cbdf95b877b889))
* apply ruff format to bridge.py to fix CI lint ([327151c](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/327151cda20a456194b1be19f884428fab0636b6))
* apply ruff format to test_agent_instruction_files.py ([a233860](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a2338605d1e6852dbbc421293e84fca34a415c90))
* apply ruff formatting to conftest.py and test_protocol.py ([dccc761](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dccc76167b29b567833e93de7cade96a7accfa1e))
* apply ruff formatting to conftest.py and test_protocol.py ([6ed1a5f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/6ed1a5f0d3d406d5b66f7cad800d314f8a1ecc47))
* **ci:** handle missing bridge/uxp-plugin in release workflow ([c64fe21](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c64fe211dbaa1282a62e502df844e143a6893e8c))
* **ci:** isolate workflow_dispatch from push concurrency in release workflow ([#12](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/12)) ([b482f06](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b482f065a0092f6b74eb3eb9842f98e826061dc2))
* correct lint_skills.py path resolution (scripts/scripts double nesting), update cli.py ([958fb14](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/958fb148a476d9c45d746e5842022434e6a37eaa))
* correct release-please README path to uppercase README.md ([b21ee68](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b21ee689b0077edd12411034521081309cb379a7))
* correct skill count and remove broken references in README ([dbb7e83](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/dbb7e832c26c61ba9bb5610530710a5926672408))
* implement BridgeRpcServer, add _posix_sidecar_launcher and pack lint ([4b4fd99](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4b4fd9912589c72c9c0090c92f09a767db978d2d))
* remove hardcoded version URLs, add README to release-please extra-files ([0387c5d](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0387c5d70579446000b01e88f2070128ec2702f6))
* remove pip install step from Quick Start — everything is bundled in .ccx ([ac446d7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/ac446d7d60c29d96adb4d49e77db19b5ab163fab))
* remove pip install step from Quick Start — everything is bundled in .ccx ([b6d621b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b6d621bb6e3ad44cd723f45186329ba5070cacff))
* remove stale PhotoshopBridgePlugin imports from __init__.py ([a65ac35](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a65ac35aadda18b1fac8358350b7a0ab57f176c3))
* remove unused pathlib.Path import to pass ruff F401 lint ([3969c2f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/3969c2ffb4afc3241152f7884fb310d6ec9d8ce4))
* remove unused pathlib.Path import to pass ruff F401 lint ([5ffc642](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/5ffc642a2264465b065dc0cc857efdaba1bbfdab))
* remove unused socketserver import, restore missing _update_manifest_version ([676213c](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/676213c986adf32c0a08d1388df8f98b1d0e3d44))
* resolve ruff lint and format issues in photoshop-setup scripts ([43684df](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/43684dfcc204e14803173165ab0faf95b6335e03))
* resolve ruff lint errors (F401, I001, B904) ([262d43f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/262d43fb6c6534c60b7e08cf5b26de8e437aaeeb))
* resolve ruff lint errors (F401, I001, B904) ([74da278](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/74da278bfd1a2c180e15b7584a1f4b62b0b6abc5))
* restore _hidden_vbs_launcher, _sidecar_launcher, _sidecar_stopper to pack_plugin.py ([75d3761](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/75d3761568c7e076a5370cabb75413cac499a98b))
* restore sidecar helper functions to pack_plugin.py ([ee6bdea](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/ee6bdeaebb2481f2ff03418d7658febdfdedec24))
* restrict release workflow builds to tag push only ([4a60114](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4a6011454cb24bf95d2d7b09e99c0889d36cbedd))
* ruff format src/ tests/ ([a4f756f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/a4f756f29b10cd871cb4a27e49b69a131c2fc4ca))
* ruff import organization in test_agent_instruction_files.py ([578fb45](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/578fb454c173fa699fcf928478a8e1321ff4b479))
* run ruff format on configure_mcp_client.py to pass CI lint ([b65a4b7](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b65a4b7ca48b27de60330328e1c0c1af0cfd2abd))
* run ruff format on configure_mcp_client.py to pass CI lint ([86e5260](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/86e5260ff56dc1457065856ddcadda444d2a1eaf))
* standalone binary build for dcc-mcp-photoshop (PyOxidizer fixes) ([db108a0](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/db108a0ebcb7f47a1d81e538d24716bc33820e6d))
* sync manifest.json version and add release version validation ([#50](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/50)) ([c2e7514](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c2e7514417a0c1e565b01cdca67670ac9f208529))
* update capability tests for adobepy_broker migration ([d06b437](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d06b43778a9cfb8e382de300b418bb199bf77a60))
* update version assertion 0.1.21 -&gt; 0.1.23 in test_import ([8b6499e](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/8b6499efa950310c88be3b8c94a2ff20bac032e8))
* use concurrent.futures.TimeoutError for cross-version compat ([07bbae4](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/07bbae4144d81d79a93519c8f5c38d2cd181cac8))
* use uppercase README filenames and unify MCP config to gateway URL ([41427d5](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/41427d5df951c8f5766cf6df4d5c76b9518337c0))


### Code Refactoring

* migrate PhotoshopMcpServer to extend DccServerBase (4-seam controller PIP-688) ([c36f85f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/c36f85ff33a8d20d5adf3a44bb73a2c3feb11cda))


### Documentation

* add agent-facing docs and fix stale references ([5764eb3](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/5764eb35f3f2ff934729302ce9ebc3db15ead480))
* add bilingual quick-start to README with plugin install and gateway config ([b77057d](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b77057dbd542e2c12cda13c61ff6fb9d109e21a5))
* add bilingual quick-start to README with plugin install and gateway config ([78f79eb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/78f79eb053377ea2b65f44bf543375328352160f))
* add one-click installer docs and install/upgrade/uninstall/rollback examples ([872d764](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/872d7641c7135d9b920e7cf8fb55cf930c5ad377))
* unify gateway URL to /mcp endpoint in README ([7ff4655](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7ff4655092a873a7c23519f2f2d3a07b7a0f4884))
* unify gateway URL to /mcp endpoint in README ([8fb515e](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/8fb515e92cae41adcd7d73361966bdff14000e42))
* update README with comprehensive MCP installation and configuration guide ([e7e5dd0](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/e7e5dd06ef230d9c43592fefb931655803d80cea))

## [0.1.23](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.22...v0.1.23) (2026-06-17)


### Features

* stability improvements toward Maya parity (PIP-1775) ([0d78bcb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0d78bcb07a0526c69f7cedaa37606f45b0e95c86))
* stability improvements toward Maya parity (PIP-1775) ([63f2648](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/63f26482e3480fed2eaf15881e9b579fcde65188))
* stability improvements toward Maya parity (PIP-1775) ([#60](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/60)) ([0d78bcb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/0d78bcb07a0526c69f7cedaa37606f45b0e95c86))

## [0.1.22](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.21...v0.1.22) (2026-06-17)


### Bug Fixes

* **ci:** handle missing bridge/uxp-plugin in release workflow ([4036633](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/403663398c4cf121f19ac1d225d91c92d28fe795))

## [0.1.21](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.20...v0.1.21) (2026-06-16)


### Features

* PIP-673 adapter capabilities and code convergence ([74b35ca](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/74b35ca616bb75bc1bb140c59aa1fba53764517a))


### Bug Fixes

* remove stale PhotoshopBridgePlugin imports from __init__.py ([aba678b](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/aba678bc2b11891587ca23af9507bf2dcbc06003))
* ruff format src/ tests/ ([b4d22cb](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/b4d22cb147d8d4d63e9ddcc0def21fd4a7149040))
* update capability tests for adobepy_broker migration ([63b45d1](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/63b45d1c2c293943d832fbae471f07455224ada2))

## [0.1.20](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.19...v0.1.20) (2026-06-16)


### Features

* add install_photoshop_connector.ps1 one-click installer + smoke check ([7d5675f](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/7d5675fd84c9b1bdc5dc3114501b5ed5dae71fa5))
* install_photoshop_connector.ps1 one-click installer + smoke check ([9be62dd](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/9be62dd67f4594fb92f577ae13b0fe4410f73ef4))


### Bug Fixes

* standalone binary build for dcc-mcp-photoshop (PyOxidizer fixes) ([4fc6e92](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/4fc6e920367625fd6cb6d1784ab32ed0856bd776))
* sync manifest.json version and add release version validation ([#50](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/50)) ([575ec44](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/575ec4477c7563143b71aa2b897583bb6d4b0da2))


### Documentation

* add one-click installer docs and install/upgrade/uninstall/rollback examples ([d50e566](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/d50e566d48329c01329cd566e279d97f4254d946))

## [0.1.19](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.18...v0.1.19) (2026-06-16)


### Bug Fixes

* add pyoxidizer installation in release build-binary job ([bbd1efc](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/bbd1efc24fad9a5ecf38cdd20a9fe78fda64b442))

## [0.1.18](https://github.com/dcc-mcp/dcc-mcp-photoshop/compare/v0.1.17...v0.1.18) (2026-06-15)


### Features

* gateway daemon-first startup, failure tracking, bridge version validation ([52f1d12](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/52f1d12f247fb620caf18a0240d1fc0100935c83))
* gateway daemon-first startup, failure tracking, bridge version validation ([#44](https://github.com/dcc-mcp/dcc-mcp-photoshop/issues/44)) ([52f1d12](https://github.com/dcc-mcp/dcc-mcp-photoshop/commit/52f1d12f247fb620caf18a0240d1fc0100935c83))

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
