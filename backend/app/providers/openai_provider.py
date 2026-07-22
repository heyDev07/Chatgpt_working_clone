from collections.abc import AsyncIterator

import tiktoken
from openai import AsyncOpenAI

from app.core.exceptions import ProviderError
from app.providers.base_provider import (
    BaseProvider,
    ChatMessage,
    FinishReason,
    GenerateResult,
    ModelInfo,
    StreamChunk,
    Usage,
)

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
    "content_filter": "content_filter",
}


def _normalize_finish_reason(reason: str | None) -> FinishReason:
    if reason is None:
        return "stop"
    return _FINISH_REASON_MAP.get(reason, "stop")


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

    async def generate(self, messages: list[ChatMessage], model: str, **kwargs) -> GenerateResult:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                **kwargs,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI generate failed: {exc}") from exc

        choice = response.choices[0]
        usage = response.usage
        return GenerateResult(
            message=ChatMessage(role="assistant", content=choice.message.content or ""),
            finish_reason=_normalize_finish_reason(choice.finish_reason),
            usage=Usage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
        )

    async def stream(self, messages: list[ChatMessage], model: str, **kwargs) -> AsyncIterator[StreamChunk]:
        try:
            response_stream = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                stream=True,
                stream_options={"include_usage": True},
                **kwargs,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI stream failed: {exc}") from exc

        try:
            async for chunk in response_stream:
                if not chunk.choices:
                    # Final usage-only chunk when stream_options.include_usage=True
                    if chunk.usage:
                        yield StreamChunk(
                            delta="",
                            usage=Usage(
                                prompt_tokens=chunk.usage.prompt_tokens,
                                completion_tokens=chunk.usage.completion_tokens,
                                total_tokens=chunk.usage.total_tokens,
                            ),
                        )
                    continue

                choice = chunk.choices[0]
                delta = choice.delta.content or ""
                finish_reason = _normalize_finish_reason(choice.finish_reason) if choice.finish_reason else None
                if delta or finish_reason:
                    yield StreamChunk(delta=delta, finish_reason=finish_reason)
        except Exception as exc:
            raise ProviderError(f"OpenAI stream interrupted: {exc}") from exc

    def count_tokens(self, text: str, model: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text))

    async def list_models(self) -> list[ModelInfo]:
        try:
            models = await self._client.models.list()
        except Exception as exc:
            raise ProviderError(f"OpenAI list_models failed: {exc}") from exc
        return [ModelInfo(id=m.id, context_window=0) for m in models.data]

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
