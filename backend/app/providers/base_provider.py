from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]
FinishReason = Literal["stop", "length", "content_filter", "error"]


@dataclass
class ChatMessage:
    role: Role
    content: str


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
    async def generate(self, messages: list[ChatMessage], model: str, **kwargs) -> GenerateResult: ...

    @abstractmethod
    def stream(self, messages: list[ChatMessage], model: str, **kwargs) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int: ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
