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
    ToolCall,
    Usage,
)

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": "stop",
    "length": "length",
    "content_filter": "content_filter",
    "tool_calls": "tool_calls",
}


def _normalize_finish_reason(reason: str | None) -> FinishReason:
    if reason is None:
        return "stop"
    return _FINISH_REASON_MAP.get(reason, "stop")


def _to_openai_message(m: ChatMessage) -> dict:
    msg: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        msg["tool_calls"] = [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in m.tool_calls
        ]
        if not m.content:
            msg["content"] = None
    if m.role == "tool":
        msg["tool_call_id"] = m.tool_call_id
    return msg


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

    async def generate(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> GenerateResult:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[_to_openai_message(m) for m in messages],
                tools=tools,
                **kwargs,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI generate failed: {exc}") from exc

        choice = response.choices[0]
        usage = response.usage
        tool_calls = (
            [
                ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
                for tc in choice.message.tool_calls
            ]
            if choice.message.tool_calls
            else None
        )
        return GenerateResult(
            message=ChatMessage(role="assistant", content=choice.message.content or "", tool_calls=tool_calls),
            finish_reason=_normalize_finish_reason(choice.finish_reason),
            usage=Usage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
        )

    async def stream(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        try:
            response_stream = await self._client.chat.completions.create(
                model=model,
                messages=[_to_openai_message(m) for m in messages],
                stream=True,
                stream_options={"include_usage": True},
                tools=tools,
                **kwargs,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI stream failed: {exc}") from exc

        # Tool-call arguments arrive fragmented across many chunks, indexed by position in the
        # tool_calls array - accumulate them here and only surface a complete ToolCall list once
        # finish_reason confirms the round is done.
        accumulator: dict[int, dict[str, str]] = {}

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

                for tc_delta in choice.delta.tool_calls or []:
                    entry = accumulator.setdefault(tc_delta.index, {"id": "", "name": "", "arguments": ""})
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        entry["name"] += tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments

                tool_calls = None
                if finish_reason == "tool_calls":
                    tool_calls = [
                        ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
                        for _, v in sorted(accumulator.items())
                    ]

                if delta or finish_reason or tool_calls:
                    yield StreamChunk(delta=delta, finish_reason=finish_reason, tool_calls=tool_calls)
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

    async def embed_texts(self, texts: list[str], model: str, **kwargs) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create(input=texts, model=model, **kwargs)
        except Exception as exc:
            raise ProviderError(f"OpenAI embed_texts failed: {exc}") from exc
        # API guarantees results are returned in the same order as the input list.
        return [item.embedding for item in response.data]
