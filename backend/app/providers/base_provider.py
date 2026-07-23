from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "length", "content_filter", "error", "tool_calls"]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as returned by the provider - parsed by the caller


@dataclass
class ChatMessage:
    role: Role
    content: str
    # Set on an assistant message that calls tools (mutually exclusive in practice with
    # meaningful content - most models emit tool_calls with empty content).
    tool_calls: list[ToolCall] | None = None
    # Set on a role="tool" message: which call this is the result of, and its tool name.
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class StreamChunk:
    delta: str
    finish_reason: FinishReason | None = None
    usage: Usage | None = None
    # Only populated on the chunk where finish_reason == "tool_calls", once every streamed
    # tool-call fragment has been accumulated into a complete call.
    tool_calls: list[ToolCall] | None = None


@dataclass
class GenerateResult:
    message: ChatMessage
    finish_reason: FinishReason
    usage: Usage


@dataclass
class ModelInfo:
    id: str
    context_window: int
    supports_streaming: bool = True
    metadata: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """Every LLM provider implements this interface. Business logic (chat_service)
    depends only on this abstraction, never on a concrete provider."""

    name: str

    @abstractmethod
    async def generate(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> GenerateResult: ...

    @abstractmethod
    def stream(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int: ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def embed_texts(self, texts: list[str], model: str, **kwargs) -> list[list[float]]: ...
