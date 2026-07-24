from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool as MCPToolInfo

from app.core.exceptions import ProviderError


@asynccontextmanager
async def get_mcp_session(server_url: str) -> AsyncIterator[ClientSession]:
    """A fresh connection per operation (matching the project's aioboto3 get_s3_client()
    pattern) rather than one long-lived session held across the app's lifetime - simpler, and
    not vulnerable to a stale/dropped connection sitting unused between tool calls."""
    async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def list_mcp_tools(server_url: str) -> list[MCPToolInfo]:
    try:
        async with get_mcp_session(server_url) as session:
            result = await session.list_tools()
            return result.tools
    except Exception as exc:
        raise ProviderError(f"MCP list_tools failed for {server_url}: {exc}") from exc


async def call_mcp_tool(server_url: str, tool_name: str, arguments: dict) -> str:
    """Returns the tool's text output, or raises if the server reports an error - the caller
    (MCPTool.run) doesn't need to know the MCP-specific result shape (content blocks,
    isError flag), matching every other BaseTool.run() in this project."""
    try:
        async with get_mcp_session(server_url) as session:
            result = await session.call_tool(tool_name, arguments)
    except Exception as exc:
        raise ProviderError(f"MCP call_tool '{tool_name}' failed: {exc}") from exc

    text_parts = [block.text for block in result.content if hasattr(block, "text")]
    output = "\n".join(text_parts)
    if result.isError:
        raise ProviderError(output or f"MCP tool '{tool_name}' returned an error")
    return output
