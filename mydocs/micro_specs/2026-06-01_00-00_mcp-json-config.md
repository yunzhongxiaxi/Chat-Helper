# MCP JSON 配置 micro-spec

## Restate
当前项目从 `config.yaml` 的 `mcp_servers` 读取 MCP 配置，但 MCP 广场给的是 JSON：`{"mcpServers": {...}}`。核心目标是让项目直接读取 JSON MCP 配置文件，避免手动转 YAML；同时确认本地 `uvx` 是否可用。

## Facts
- 当前 `backend/config.py` 只暴露 `mcp_servers` YAML 字段。
- 当前 `backend/services/mcp_tool_registry.py` 已按 `command/args/env` 启动 stdio MCP server。
- 本地 `uv` 与 `uvx` 都存在：`uv 0.10.12`，`uvx 0.10.12`。

## Scope
- 增加 MCP JSON 配置读取，默认读取 `mcp.json`，兼容顶层 `mcpServers` 格式。
- `config.mcp_servers` 优先使用 JSON 文件；没有 JSON 文件时回退 `config.yaml` 里的旧 `mcp_servers`。
- 新增项目示例 `mcp.json`，内容使用 MCP 广场 fetch server 格式。
- 不执行 `uvx mcp-server-fetch` 安装或联网拉包，仅确认命令存在。

## Change Log
- `backend/config.py` 新增 `mcp_config_path`，默认读取 `mcp.json`。
- `config.mcp_servers` 优先读取 JSON 顶层 `mcpServers`；不存在 `mcp.json` 时回退 `config.yaml` 的 `mcp_servers`。
- 新增 `mcp.json`，直接采用 MCP 广场 fetch server 配置：`uvx mcp-server-fetch`。

## Validation
- 已确认本地存在 `uv` 和 `uvx`：二者版本均为 `0.10.12`。
- 已运行：`python -m py_compile backend/config.py backend/services/mcp_tool_registry.py`，通过。
- 已运行 JSON 读取 smoke test：`Config('config.yaml', 'mcp.json').mcp_servers` 返回 `fetch` 配置。

## Resume or Handoff
当前核心目标已完成。未执行 `uvx mcp-server-fetch`，因此没有联网拉取或安装 MCP server；第一次实际调用 fetch 工具时，`uvx` 会按需解析/运行该包。