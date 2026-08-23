# dcc-mcp-photoshop

将 Adobe Photoshop 接入 DCC MCP 网关。适配器通过 adobepy Broker 与 UXP
Bridge 调用 Photoshop，不再维护独立的 9001 WebSocket 协议或 `.ccx` 包。

## 运行链路

```text
MCP 客户端 → dcc-mcp gateway (:9765) → Photoshop adapter
           → adobepy broker (:47391) → UXP bridge → Photoshop
```

## 快速开始

1. 按根目录 [Install SOP](install.md) 安装 wheel 与经过验证的 adobepy CLI，
   并通过环境变量配置 `ADOBEPY_CLI` 与 `ADOBEPY_TOKEN`。

2. 先生成计划，再执行 canonical 生命周期：

   ```powershell
   dcc-mcp-photoshop install --json --dry-run
   dcc-mcp-photoshop install --json --yes
   ```

3. 如果命令返回唯一 UXP next step，在 Photoshop 中启用 Developer Mode，
   用 Adobe UXP Developer Tool 加载报告的 `manifest.json`。

4. 验证真实 Photoshop RPC，然后启动适配器：

   ```powershell
   dcc-mcp-photoshop verify --json
   dcc-mcp-photoshop --gateway-port 9765
   ```

5. MCP 客户端连接 `http://127.0.0.1:9765/mcp`。单适配器调试可用
   `dcc-mcp-cli list` 查询实例直连地址。

## 验收标准

仅端口监听不代表链路可用。完整验收必须同时满足：

- MCP 网关或直连端口可访问；
- `http://127.0.0.1:47391/health` 返回 Broker 健康；
- Broker 至少有一个 Photoshop Bridge session；
- `get_document_info` 等真实 Photoshop 工具调用成功。

`photoshop-setup` skill 保留兼容入口，但 `setup_uxp_plugin` 只路由到
canonical CLI。文件复制不代表可用，只有真实 Photoshop RPC 成功才算完成。

## CLI

```text
dcc-mcp-photoshop [install|status|verify|uninstall|upgrade] [OPTIONS]

--json                输出 Install SOP v1 JSON
--yes                 执行变更
--dry-run             只生成计划
--dcc-path PATH       Photoshop 可执行文件覆盖
--python PATH         目标 Python 覆盖
--mcp-port PORT       可选固定实例端口，默认由操作系统分配
--broker-url URL      adobepy Broker，默认 http://127.0.0.1:47391
--gateway-port PORT   网关竞争端口
--server-name NAME    MCP 服务名
--skill-paths PATH    额外 skill 目录
--no-builtins         不加载内置 skills
--verbose, -v         调试日志
--version             输出版本
```

## 职责边界

- dcc-mcp-photoshop Release：Python wheel、源码包、平台适配器压缩包。
- adobepy Release：Broker、Python SDK、UXP Bridge 模板。
- Adobe UXP Developer Tool：开发插件注册、校验与加载。

协议与 Bridge 实现以 [adobepy](https://github.com/dcc-mcp/adobepy) 为准。
