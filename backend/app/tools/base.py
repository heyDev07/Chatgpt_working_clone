from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

PermissionLevel = Literal["public", "restricted"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    # JSON Schema for the tool's arguments - doubles as validation and as the shape sent to a
    # provider's function-calling API (Phase 6b).
    input_schema: dict[str, Any]
    permission_level: PermissionLevel = "public"
    timeout_seconds: float = 10.0


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None


class BaseTool(ABC):
    definition: ToolDefinition

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool. Raise on failure - the router turns exceptions into a failed
        ToolResult rather than letting them propagate, so tools can just raise naturally."""
        ...
