from collections.abc import AsyncIterator

from google import genai
from google.genai import types

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

_FINISH_REASON_MAP: dict[types.FinishReason, FinishReason] = {
    types.FinishReason.STOP: "stop",
    types.FinishReason.MAX_TOKENS: "length",
    types.FinishReason.SAFETY: "content_filter",
    types.FinishReason.PROHIBITED_CONTENT: "content_filter",
    types.FinishReason.SPII: "content_filter",
    types.FinishReason.BLOCKLIST: "content_filter",
    types.FinishReason.RECITATION: "content_filter",
}


def _normalize_finish_reason(reason: types.FinishReason | None) -> FinishReason:
    if reason is None:
        return "stop"
    return _FINISH_REASON_MAP.get(reason, "error")


def _split_system_and_turns(messages: list[ChatMessage]) -> tuple[str | None, list[types.Content]]:
    """Gemini takes the system prompt out-of-band and uses role 'model' (not 'assistant')."""
    system_parts = [m.content for m in messages if m.role == "system"]
    system_instruction = "\n\n".join(system_parts) if system_parts else None

    turns = [
        types.Content(role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)])
        for m in messages
        if m.role != "system"
    ]
    return system_instruction, turns


def _usage_from_metadata(usage_metadata: types.GenerateContentResponseUsageMetadata | None) -> Usage:
    if usage_metadata is None:
        return Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    return Usage(
        prompt_tokens=usage_metadata.prompt_token_count or 0,
        completion_tokens=usage_metadata.candidates_token_count or 0,
        total_tokens=usage_metadata.total_token_count or 0,
    )


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    async def generate(self, messages: list[ChatMessage], model: str, **kwargs) -> GenerateResult:
        system_instruction, turns = _split_system_and_turns(messages)
        config = types.GenerateContentConfig(system_instruction=system_instruction, **kwargs)

        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=turns, config=config
            )
        except Exception as exc:
            raise ProviderError(f"Gemini generate failed: {exc}") from exc

        candidate = response.candidates[0] if response.candidates else None
        return GenerateResult(
            message=ChatMessage(role="assistant", content=response.text or ""),
            finish_reason=_normalize_finish_reason(candidate.finish_reason if candidate else None),
            usage=_usage_from_metadata(response.usage_metadata),
        )

    async def stream(self, messages: list[ChatMessage], model: str, **kwargs) -> AsyncIterator[StreamChunk]:
        system_instruction, turns = _split_system_and_turns(messages)
        config = types.GenerateContentConfig(system_instruction=system_instruction, **kwargs)

        try:
            response_stream = await self._client.aio.models.generate_content_stream(
                model=model, contents=turns, config=config
            )
        except Exception as exc:
            raise ProviderError(f"Gemini stream failed: {exc}") from exc

        try:
            async for chunk in response_stream:
                candidate = chunk.candidates[0] if chunk.candidates else None
                finish_reason = (
                    _normalize_finish_reason(candidate.finish_reason)
                    if candidate and candidate.finish_reason
                    else None
                )
                usage = _usage_from_metadata(chunk.usage_metadata) if finish_reason else None
                delta = chunk.text or ""
                if delta or finish_reason:
                    yield StreamChunk(delta=delta, finish_reason=finish_reason, usage=usage)
        except Exception as exc:
            raise ProviderError(f"Gemini stream interrupted: {exc}") from exc

    def count_tokens(self, text: str, model: str) -> int:
        # Gemini's tokenizer is a network call; the BaseProvider interface keeps this
        # synchronous to match OpenAI's local tiktoken count, so we use the sync client here.
        try:
            response = self._client.models.count_tokens(model=model, contents=text)
        except Exception as exc:
            raise ProviderError(f"Gemini count_tokens failed: {exc}") from exc
        return response.total_tokens or 0

    async def list_models(self) -> list[ModelInfo]:
        try:
            models = []
            async for m in await self._client.aio.models.list():
                models.append(
                    ModelInfo(
                        id=(m.name or "").removeprefix("models/"),
                        context_window=m.input_token_limit or 0,
                    )
                )
            return models
        except Exception as exc:
            raise ProviderError(f"Gemini list_models failed: {exc}") from exc

    async def health_check(self) -> bool:
        try:
            await self._client.aio.models.list()
            return True
        except Exception:
            return False
