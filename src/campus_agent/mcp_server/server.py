"""MCP stdio server entry point for CampusTrain tools."""

from __future__ import annotations

import asyncio

from mcp.server.mcpserver import MCPServer

from campus_agent.campus_client.client import CampusTrainClient
from campus_agent.config import Settings
from campus_agent.mcp_server.tools import register_tools


def create_server(client: CampusTrainClient) -> MCPServer:
    server = MCPServer(
        name="campus-agent",
        version="0.1.0",
        description="CampusTrain business tools; writes require Agent confirmation",
        log_level="WARNING",
    )
    return register_tools(server, client)


async def run_stdio() -> None:
    settings = Settings()
    client = CampusTrainClient(
        str(settings.gateway_url),
        settings.jwt_token.get_secret_value(),
        timeout=settings.http_timeout_seconds,
    )
    server = create_server(client)
    try:
        await server.run_stdio_async()
    finally:
        await client.aclose()


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
