from typing import Any

from app.mcp.client import call_mcp_tool
from app.tools.base import BaseTool, ToolDefinition

# Web search and similar MCP calls go over the network to a third-party server, unlike the
# in-process calculator - a longer default timeout than the native tools' matters here.
MCP_TOOL_TIMEOUT_SECONDS = 20.0


class MCPTool(BaseTool):
    """Adapts one tool discovered from an MCP server into our own BaseTool interface, so
    ToolRouter/ToolRegistry/chat_service never need to know a given tool came from MCP rather
    than being written natively (like the calculator) - it's just another entry in the same
    registry, audited and timeout-enforced the same way."""

    def __init__(self, definition: ToolDefinition, server_url: str):
        self.definition = definition
        self._server_url = server_url

    async def run(self, **kwargs: Any) -> str:
        return await call_mcp_tool(self._server_url, self.definition.name, kwargs)
