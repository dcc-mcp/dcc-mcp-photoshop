# dcc-mcp-photoshop

Adobe Photoshop 的 [DCC Model Context Protocol](https://github.com/dcc-mcp/dcc-mcp-core) (MCP) 生态系统插件。

通过 UXP WebSocket 插件，将 Photoshop 转变为符合标准的 **MCP Streamable HTTP 服务器**。AI 助手可通过类型化工具查看文档、创建和编辑图层、处理文本、导出图像以及自动化 Photoshop 工作流。

[![CI](https://github.com/dcc-mcp/dcc-mcp-photoshop/actions/workflows/ci.yml/badge.svg)](https://github.com/dcc-mcp/dcc-mcp-photoshop/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/dcc-mcp/dcc-mcp-photoshop/graph/badge.svg)](https://codecov.io/gh/dcc-mcp/dcc-mcp-photoshop)
[![GitHub release](https://img.shields.io/github/v/release/dcc-mcp/dcc-mcp-photoshop?label=release)](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases)
[![PyPI](https://img.shields.io/pypi/v/dcc-mcp-photoshop?label=PyPI)](https://pypi.org/project/dcc-mcp-photoshop/)
[![Python](https://img.shields.io/pypi/pyversions/dcc-mcp-photoshop?label=Python)](https://pypi.org/project/dcc-mcp-photoshop/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 架构

```
AI Agent (Claude Desktop / Cursor / Copilot)
    │  MCP Streamable HTTP (port 8765)
    ▼
PhotoshopMcpServer  [Python]
    │  WebSocket JSON-RPC (port 9001)
    ▼
UXP Plugin  [bridge/uxp-plugin/, JavaScript]
    │  Photoshop UXP API
    ▼
Adobe Photoshop 2022+
```

**关键架构决策：**
- Python 在 9001 端口运行 **WebSocket 服务器**，UXP 插件作为 **WebSocket 客户端** 连接（UXP 仅支持客户端模式）。
- MCP 服务器（HTTP，8765 端口）和 WebSocket bridge 可以在同一进程内运行（嵌入式模式，仅开发用），也可以分离运行（网关模式，推荐用于部署）。
- 所有 Photoshop 自动化操作通过 [adobepy](https://github.com/dcc-mcp/adobepy) 外观层进行，该层封装了 WebSocket bridge。

## 安装

### PyPI

```bash
pip install "dcc-mcp-photoshop[sidecar]"
```

### 独立二进制文件

从 [GitHub Releases](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases) 下载平台对应的二进制文件，无需 Python 运行时。

### UXP .ccx 插件

1. 从 [最新发布](https://github.com/dcc-mcp/dcc-mcp-photoshop/releases) 下载 `.ccx` 文件
2. 打开 **Creative Cloud Desktop** → **Plugins** → **Manage Plugins**
3. 点击齿轮图标 → **Install from file...**
4. 选择下载的 `.ccx` 文件
5. 重启 Photoshop

## 快速开始

安装 UXP 插件并重启 Photoshop 后，插件会自动启动内置 sidecar（bridge + MCP 服务器）。

将 MCP 客户端指向 `http://127.0.0.1:8765/mcp`。

### Claude Desktop 配置

```json
{
  "mcpServers": {
    "photoshop": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

### 测试提示

```text
列出当前 Photoshop 文档中的所有图层，然后创建一个内容为 "Hello World" 的文本图层。
```

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|----------|-------------|---------|
| `DCC_MCP_REGISTRY_DIR` | 网关发现共享 FileRegistry 目录 | `~/.dcc-mcp/registry` |
| `DCC_MCP_PHOTOSHOP_SKILL_PATHS` | 额外技能目录（冒号分隔） | — |
| `DCC_MCP_SKILL_PATHS` | 全局额外技能目录 | — |
| `DCC_MCP_GATEWAY_PORT` | 网关竞争端口 | `9765` |

## 内置技能

dcc-mcp-photoshop 附带 **4 个技能包**，包含 **20+ 个工具**，按领域组织。
技能采用**懒加载**机制：初始仅提供元工具；使用 MCP `load_skill` 工具加载所需的技能包。

### photoshop-document

文档信息与图层列表。

| 工具 | 说明 | 只读 |
|------|------|------|
| `get_document_info` | 获取当前 Photoshop 文档的元数据（名称、尺寸、分辨率、色彩模式） | ✅ |
| `list_layers` | 列出当前文档中的所有图层 | ✅ |

### photoshop-image

建文档、导出、画布/图像调整、拼合与合并操作。

| 工具 | 说明 | 只读 |
|------|------|------|
| `create_document` | 创建指定尺寸、分辨率和色彩模式的新文档 | ❌ |
| `export_document` | 导出当前文档为 PNG/JPG/TIFF/PSD | ❌ |
| `save_document` | 保存当前文档 | ❌ |
| `resize_canvas` | 调整画布大小（不缩放内容） | ❌ |
| `resize_image` | 缩放图像（重采样内容） | ❌ |
| `flatten_image` | 将所有图层拼合为单个背景图层 | ❌ |
| `merge_visible_layers` | 合并所有可见图层 | ❌ |

### photoshop-layers

图层的完整 CRUD 以及视觉属性修改。

| 工具 | 说明 | 只读 |
|------|------|------|
| `create_layer` | 创建像素、组或调整图层 | ❌ |
| `delete_layer` | 按名称删除图层 | ❌ |
| `duplicate_layer` | 复制图层 | ❌ |
| `rename_layer` | 重命名图层 | ❌ |
| `set_layer_opacity` | 设置图层不透明度（0-100） | ❌ |
| `set_layer_visibility` | 显示或隐藏图层 | ❌ |
| `set_layer_blend_mode` | 设置混合模式（27 种模式） | ❌ |
| `fill_layer` | 使用纯色（十六进制）或透明填充图层 | ❌ |

### photoshop-text

文本图层的创建、编辑和检查。

| 工具 | 说明 | 只读 |
|------|------|------|
| `create_text_layer` | 创建带内容和样式的新文本图层 | ❌ |
| `update_text_layer` | 更新现有文本图层的内容或样式 | ❌ |
| `get_text_layer_info` | 获取文本图层的文本内容和样式属性 | ✅ |

## 一键安装配置

加载 `photoshop-setup` 技能即可自动化全流程：

```text
load_skill("photoshop-setup")
```

| 工具 | 说明 |
|------|------|
| `check_environment` | 检查系统环境 |
| `install_package` | 通过 pip 安装 |
| `setup_uxp_plugin` | 安装 UXP .ccx 插件 |
| `start_server` | 启动服务器（开发模式） |
| `verify_connection` | 验证 bridge 连接 |
| `configure_mcp_client` | 自动配置 MCP 客户端 |

工作流：`check_environment` → `setup_uxp_plugin` → `configure_mcp_client` → 完成。

## Bridge 协议

Python ↔ UXP 通信使用 JSON-RPC 2.0 通过 WebSocket 连接进行。Python 作为服务器（端口 9001）；UXP 插件作为客户端连接。

### 握手

连接时，UXP 插件发送 `hello` 消息：

```json
{"type": "hello", "protocol": "photoshop-bridge", "version": "0.1.0", "client": "photoshop-uxp", "reconnect": false}
```

Python 回复 `hello_ack`：

```json
{"type": "hello_ack", "protocol": "photoshop-bridge", "version": "0.1.0"}
```

### RPC 调用

**Python → UXP：**

```json
{"jsonrpc": "2.0", "id": 1, "method": "ps.listLayers", "params": {"include_hidden": true}}
```

**UXP → Python（成功）：**

```json
{"jsonrpc": "2.0", "id": 1, "result": [
  {"name": "Background", "type": "pixel", "visible": true, "opacity": 100}
]}
```

**UXP → Python（错误）：**

```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "No active document"}}
```

### 支持的 RPC 方法

| 方法 | 说明 |
|--------|------|
| `ps.getDocumentInfo` | 获取活动文档元数据 |
| `ps.listDocuments` | 列出所有打开的文档 |
| `ps.createDocument` | 创建新文档 |
| `ps.saveDocument` | 保存活动文档 |
| `ps.closeDocument` | 关闭文档 |
| `ps.exportDocument` | 导出为 PNG/JPG/TIFF/PSD |
| `ps.resizeCanvas` | 调整画布大小 |
| `ps.resizeImage` | 缩放图像 |
| `ps.flattenImage` | 拼合所有图层 |
| `ps.mergeVisibleLayers` | 合并可见图层 |
| `ps.listLayers` | 列出图层 |
| `ps.createLayer` | 创建图层 |
| `ps.deleteLayer` | 删除图层 |
| `ps.setLayerVisibility` | 显示/隐藏图层 |
| `ps.renameLayer` | 重命名图层 |
| `ps.setLayerOpacity` | 设置不透明度 |
| `ps.duplicateLayer` | 复制图层 |
| `ps.setLayerBlendMode` | 设置混合模式 |
| `ps.fillLayer` | 填充纯色 |
| `ps.createTextLayer` | 创建文本图层 |
| `ps.updateTextLayer` | 更新文本图层 |
| `ps.getTextLayerInfo` | 获取文本图层属性 |
| `ps.executeScript` | 执行 JS 表达式 |
| `ps.executeAction` | 执行 Photoshop 动作 |

## 技能编写

推荐使用 `adobepy` 外观层编写技能：

```python
from adobe.dcc_mcp import action_result
from adobe.photoshop import Photoshop
from dcc_mcp_core.skill import skill_entry


@skill_entry
def list_layers(**kwargs) -> dict:
    """列出当前 Photoshop 文档中的所有图层。"""
    app = Photoshop()
    return action_result(
        "已列出活动 Photoshop 图层",
        lambda: {"layers": [layer.name for layer in app.activeLayers]},
    )
```

### 技能目录结构

```
skills/
├── photoshop-document/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
├── photoshop-image/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
├── photoshop-layers/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
├── photoshop-text/
│   ├── SKILL.md
│   ├── tools.yaml
│   └── scripts/
```

## CLI 参考

```
dcc-mcp-photoshop [OPTIONS]

选项：
  --embedded          嵌入式模式：单进程运行 MCP 服务器 + bridge
  --mcp-port PORT     MCP HTTP 服务器端口（默认：8765）
  --ws-port PORT      WebSocket bridge 端口（默认：9001）
  --ws-host HOST      WebSocket 绑定地址（默认：localhost）
  --rpc-port PORT     HTTP RPC 服务器端口（默认：9100）
  --gateway-port PORT 网关竞争端口（默认：9765）
  --server-name NAME  MCP initialize 中的服务器名称
  --skill-paths PATH  额外技能目录
  --no-builtins       不发现内置技能
  --verbose, -v       开启调试日志
  --version           显示版本并退出
```

## Python API

```python
import dcc_mcp_photoshop

handle = dcc_mcp_photoshop.start_server(port=8765, ws_port=9001)
print(f"MCP URL: {handle.mcp_url()}")
handle.shutdown()
```

## 网关模式（推荐用于部署）

**终端 1** — 启动 MCP 服务器：

```bash
dcc-mcp-server --dcc photoshop --mcp-port 8765 --gateway-port 9765
```

**终端 2** — 启动 bridge 插件：

```bash
python -m dcc_mcp_photoshop
```

MCP 客户端连接到 `http://127.0.0.1:8765/mcp`（直连）或 `http://127.0.0.1:9765/mcp`（网关聚合）。

## 开发

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-photoshop.git
cd dcc-mcp-photoshop
pip install -e ".[dev]"
pytest tests/
```

## 要求

- **Photoshop**：Adobe Photoshop 2022+（需要 UXP 支持）
- **Python**（pip 安装方式）：Python 3.8+
- **依赖**（pip 自动安装）：
  - `dcc-mcp-core >= 0.18.14, < 1.0.0`
  - `adobepy >= 0.1.0`
  - `websockets >= 12.0`

## 版本兼容性

| dcc-mcp-photoshop | dcc-mcp-core | UXP 插件 | Sidecar 二进制 |
|-------------------|-------------|----------|----------------|
| 0.1.x | >=0.12.14,<1.0.0 | 0.1.x | dcc-mcp-server >=0.12.14 |
| 0.2.x（计划中） | >=0.18.2,<1.0.0 | 0.2.x | dcc-mcp-server >=0.18.2 |

## 常见问题

### UXP 插件无法连接

1. 确保 Photoshop 2022+ 正在运行
2. 检查插件是否已加载：**Plugins** → **Development** → **Load Plugin...** → 选择 `manifest.json`
3. 确认面板显示 "Connected" 状态
4. 检查 bridge 日志文件：`~/.dcc-mcp/logs/photoshop-bridge.log`

### WebSocket 连接被拒绝

1. 先启动 Python bridge：`dcc-mcp-photoshop --embedded`
2. 然后在 Photoshop 中加载 UXP 插件（或重启已启用插件的 Photoshop）
3. UXP 插件会自动连接到 `ws://localhost:9001`

### 无活动文档错误

1. 在 Photoshop 中打开文档（File → New 或 File → Open）
2. 等待 bridge 状态显示文档名称
3. 重试技能调用

### 防火墙阻止端口

默认端口：
- `8765` — MCP HTTP 服务器
- `9001` — WebSocket bridge（Python ↔ UXP）
- `9100` — HTTP RPC 服务器
- `9765` — 网关竞争端口

## 路线图

### v0.1.0 — 基础功能 ✅
- 包结构和 API 设计
- PhotoshopBridge WebSocket 客户端框架
- 技能编写辅助工具
- UXP 插件架构设计

### v0.2.0 — UXP 插件 + Bridge ✅
- UXP 插件 WebSocket 客户端（JavaScript）
- Python bridge WebSocket 服务器
- JSON-RPC 2.0 协议实现
- 发布渠道（pip、二进制、.ccx）
- 20+ Photoshop 技能
- 跨进程 RPC bridge

### v0.3.0 — 技能与打磨（下一步）
- 智能对象支持
- 选区工具（选框、魔棒）
- 滤镜应用（模糊、锐化等）
- 色彩调整（色阶、曲线、色相/饱和度）
- 批处理

### v1.0.0 — 生产就绪
- Photoshop 2025+ UXP API 兼容性
- 性能优化
- 认证与安全加固

## 贡献

特别欢迎具有以下经验的贡献者：
- Adobe UXP / ExtendScript 经验
- Photoshop 自动化知识
- WebSocket 和 JSON-RPC 协议经验

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解指南。

## 许可证

MIT — 参见 [LICENSE](LICENSE)。
