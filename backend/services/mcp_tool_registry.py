import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.config import config


class MCPToolRegistry:
    def __init__(self):
        self._tool_servers: dict[str, str] = {}

    async def get_tool_definitions(self) -> list[dict[str, Any]]:
        tool_definitions = []
        self._tool_servers = {}

        for server_name, server_config in config.mcp_servers.items():
            tools = await self._list_server_tools(server_config)
            for tool in tools:
                tool_name = tool.name
                if tool_name in self._tool_servers:
                    existing_server = self._tool_servers[tool_name]
                    raise ValueError(f"MCP 工具名冲突: {tool_name} 同时由 {existing_server} 和 {server_name} 提供")

                self._tool_servers[tool_name] = server_name
                tool_definitions.append(self._to_openai_tool(tool))

        return tool_definitions

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        server_name = self._tool_servers.get(tool_name)
        if not server_name:
            await self.get_tool_definitions()
            server_name = self._tool_servers.get(tool_name)

        if not server_name:
            raise ValueError(f"MCP 工具不可用: {tool_name}")

        server_config = config.mcp_servers[server_name]
        async with self._create_session(server_config) as session:
            result = await session.call_tool(tool_name, arguments)
            return self._format_result(result)

    async def _list_server_tools(self, server_config: dict[str, Any]):
        async with self._create_session(server_config) as session:
            response = await session.list_tools()
            return response.tools

    def _create_session(self, server_config: dict[str, Any]):
        return _MCPSessionContext(server_config)

    def _to_openai_tool(self, tool) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema or {"type": "object", "properties": {}},
            },
        }

    def _format_result(self, result) -> str:
        content = getattr(result, "content", None)
        if not content:
            return "工具未返回内容"

        parts = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
            else:
                parts.append(str(item))

        return "\n".join(parts) if parts else "工具未返回内容"


class _MCPSessionContext:
    def __init__(self, server_config: dict[str, Any]):
        self._server_config = server_config
        self._stdio_context = None
        self._session_context = None

    async def __aenter__(self) -> ClientSession:
        server_params = StdioServerParameters(
            command=self._server_config["command"],
            args=self._server_config.get("args", []),
            env=self._build_env(),
        )
        self._stdio_context = stdio_client(server_params)
        read, write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(read, write)
        session = await self._session_context.__aenter__()
        await session.initialize()
        return session

    async def __aexit__(self, exc_type, exc, tb):
        if self._session_context:
            await self._session_context.__aexit__(exc_type, exc, tb)
        if self._stdio_context:
            await self._stdio_context.__aexit__(exc_type, exc, tb)

    def _build_env(self) -> dict[str, str] | None:
        env_config = self._server_config.get("env")
        if not env_config:
            return None

        env = dict(os.environ)
        for key, value in env_config.items():
            env[key] = os.environ.get(key, value)
        return env


def extract_tool_call(response) -> tuple[str, dict[str, Any]] | None:
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_call = response.tool_calls[0]
        return tool_call.function.name, json.loads(tool_call.function.arguments or "{}")

    function_call = getattr(response, "function_call", None)
    if function_call:
        args = dict(function_call.args) if function_call.args else {}
        return function_call.name, args

    return None


mcp_tool_registry = MCPToolRegistry()
