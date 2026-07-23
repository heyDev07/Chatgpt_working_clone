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

    def list_openai_tool_schemas(self) -> list[dict]:
        """OpenAI-function-calling-shaped tool schemas - the one format chat_service and the
        providers agree on; GeminiProvider translates from this shape internally rather than
        the registry needing to know about every provider's own format."""
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
        ]


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry([CalculatorTool()])
