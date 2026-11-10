from __future__ import annotations

import os
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpBridge:
    def __init__(self, root: Path, gateway_jwt: str, gateway_url: str) -> None:
        self.root, self.jwt, self.gateway = root, gateway_jwt, gateway_url
        self.schemas: dict[str, Any] = {}
        self._jwt_context: ContextVar[str] = ContextVar("mcp_jwt", default="")

    def set_jwt(self, token: str):
        return self._jwt_context.set(token)

    def reset_jwt(self, token) -> None:
        self._jwt_context.reset(token)

    async def discover(self) -> list[str]:
        async with stdio_client(self._params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
        self.schemas = {
            tool.name: {
                "description": tool.description or f"CampusTrain MCP 工具 {tool.name}",
                "input_schema": tool.input_schema,
            }
            for tool in result.tools
        }
        return list(self.schemas)

    async def call(self, name: str, args: dict[str, Any], jwt: str) -> Any:
        env = os.environ.copy()
        env["CAMPUS_AGENT_JWT_TOKEN"] = jwt or self._jwt_context.get()
        env["CAMPUS_AGENT_GATEWAY_URL"] = self.gateway
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "campus_agent.mcp_server.server"],
            cwd=str(self.root),
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=args)
                return result.structured_content or {
                    "content": [getattr(x, "text", str(x)) for x in result.content]
                }

    def _params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "campus_agent.mcp_server.server"],
            cwd=str(self.root),
            env={**os.environ, "CAMPUS_AGENT_GATEWAY_URL": self.gateway},
        )
