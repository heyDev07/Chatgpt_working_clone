import logging
from functools import lru_cache

from app.config.settings import get_settings
from app.mcp.client import list_mcp_tools
from app.tools.base import BaseTool, ToolDefinition
from app.tools.calculator import CalculatorTool
from app.tools.mcp_tool import MCP_TOOL_TIMEOUT_SECONDS, MCPTool

logger = logging.getLogger("app.tools")


class ToolRegistry:
    def __init__(self, tools: list[BaseTool] | None = None):
        self._tools: dict[str, BaseTool] = {tool.definition.name: tool for tool in (tools or [])}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def list_openai_tool_schemas(self, allowed: frozenset[str] | None = None) -> list[dict]:
        """OpenAI-function-calling-shaped tool schemas - the one format chat_service and the
        providers agree on; GeminiProvider translates from this shape internally rather than
        the registry needing to know about every provider's own format. `allowed` restricts the
        result to a subset (e.g. an agent persona's allowed_tools) - None means every registered
        tool."""
        return [
            {
                "type": "function",
                "function": {
                    "name": d.name,
                    "description": d.description,
                    "parameters": d.input_schema,
                },
            }
            for d in self.list_definitions()
            if allowed is None or d.name in allowed
        ]


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry([CalculatorTool()])


async def register_mcp_servers() -> None:
    """Called once at app startup (see main.py's lifespan, alongside ensure_bucket_exists() /
    ensure_collection()) - discovers each configured MCP server's tools and adds them to the
    shared registry. Best-effort per server: a server being unreachable at startup should log
    and continue, not crash the app or block the other (native or MCP) tools from being
    available."""
    settings = get_settings()
    registry = get_tool_registry()

    if settings.tavily_api_key:
        server_url = f"{settings.tavily_mcp_url}?tavilyApiKey={settings.tavily_api_key}"
        try:
            mcp_tools = await list_mcp_tools(server_url)
            for mcp_tool in mcp_tools:
                registry.register(
                    MCPTool(
                        ToolDefinition(
                            name=mcp_tool.name,
                            description=mcp_tool.description or "",
                            input_schema=mcp_tool.inputSchema,
                            timeout_seconds=MCP_TOOL_TIMEOUT_SECONDS,
                        ),
                        server_url=server_url,
                    )
                )
            logger.info("Registered %d tool(s) from Tavily MCP server", len(mcp_tools))
        except Exception:
            logger.exception("Failed to connect to Tavily MCP server - its tools are unavailable")
