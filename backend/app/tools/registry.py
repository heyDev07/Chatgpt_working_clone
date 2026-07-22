from functools import lru_cache

from app.tools.base import BaseTool, ToolDefinition
from app.tools.calculator import CalculatorTool


class ToolRegistry:
    def __init__(self, tools: list[BaseTool] | None = None):
        self._tools: dict[str, BaseTool] = {tool.definition.name: tool for tool in (tools or [])}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry([CalculatorTool()])
