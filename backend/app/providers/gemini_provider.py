import json
import uuid
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
    ToolCall,
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


def _safe_json_dict(content: str) -> dict:
    """Tool results are stored on ChatMessage.content as a JSON string (matching the OpenAI
    convention used throughout chat_service); Gemini's FunctionResponse wants an actual dict."""
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"result": content}


def _split_system_and_turns(messages: list[ChatMessage]) -> tuple[str | None, list[types.Content]]:
    """Gemini takes the system prompt out-of-band and uses role 'model' (not 'assistant').
    Gemini also has no separate "tool" role - function responses go in a user-role turn, and
    an assistant message with tool_calls becomes a model-role turn of function_call parts
    instead of a text part."""
    system_parts = [m.content for m in messages if m.role == "system"]
    system_instruction = "\n\n".join(system_parts) if system_parts else None

    turns: list[types.Content] = []
    for m in messages:
        if m.role == "system":
            continue
        if m.role == "assistant" and m.tool_calls:
            parts = [
                types.Part(
                    function_call=types.FunctionCall(
                        id=tc.id, name=tc.name, args=json.loads(tc.arguments or "{}")
                    )
                )
                for tc in m.tool_calls
            ]
            turns.append(types.Content(role="model", parts=parts))
        elif m.role == "tool":
            turns.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=m.tool_call_id, name=m.name or "", response=_safe_json_dict(m.content)
                            )
                        )
                    ],
                )
            )
        else:
            turns.append(
                types.Content(role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)])
            )
    return system_instruction, turns


def _to_gemini_tools(tools: list[dict] | None) -> list[types.Tool] | None:
    """Translates the provider-agnostic OpenAI-function-calling-shaped tool schemas that
    chat_service builds (see ToolRegistry.list_openai_tool_schemas) into Gemini's shape, so
    the tool registry only needs to know one schema format."""
    if not tools:
        return None
    declarations = [
        types.FunctionDeclaration(
            name=t["function"]["name"],
            description=t["function"]["description"],
            parameters_json_schema=t["function"]["parameters"],
        )
        for t in tools
    ]
    return [types.Tool(function_declarations=declarations)]


def _extract_tool_calls(candidate: types.Candidate | None) -> list[ToolCall] | None:
    if not candidate or not candidate.content or not candidate.content.parts:
        return None
    calls = [
        ToolCall(
            id=part.function_call.id or str(uuid.uuid4()),
            name=part.function_call.name or "",
            arguments=json.dumps(part.function_call.args or {}),
        )
        for part in candidate.content.parts
        if part.function_call
    ]
    return calls or None


_KWARG_TRANSLATION = {"max_tokens": "max_output_tokens"}


def _translate_kwargs(kwargs: dict) -> dict:
    """The generation kwargs chat_service builds use provider-agnostic names
    (temperature/max_tokens/top_p); Gemini's SDK expects max_output_tokens instead of
    max_tokens, so translate here rather than leaking Gemini-specific names upstream."""
    return {_KWARG_TRANSLATION.get(key, key): value for key, value in kwargs.items()}


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

    async def generate(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> GenerateResult:
        system_instruction, turns = _split_system_and_turns(messages)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction, tools=_to_gemini_tools(tools), **_translate_kwargs(kwargs)
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=turns, config=config
            )
        except Exception as exc:
            raise ProviderError(f"Gemini generate failed: {exc}") from exc

        candidate = response.candidates[0] if response.candidates else None
        tool_calls = _extract_tool_calls(candidate)
        finish_reason = "tool_calls" if tool_calls else _normalize_finish_reason(candidate.finish_reason if candidate else None)
        return GenerateResult(
            message=ChatMessage(role="assistant", content=response.text or "", tool_calls=tool_calls),
            finish_reason=finish_reason,
            usage=_usage_from_metadata(response.usage_metadata),
        )

    async def stream(
        self, messages: list[ChatMessage], model: str, tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        system_instruction, turns = _split_system_and_turns(messages)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction, tools=_to_gemini_tools(tools), **_translate_kwargs(kwargs)
        )

        try:
            response_stream = await self._client.aio.models.generate_content_stream(
                model=model, contents=turns, config=config
            )
        except Exception as exc:
            raise ProviderError(f"Gemini stream failed: {exc}") from exc

        try:
            async for chunk in response_stream:
                candidate = chunk.candidates[0] if chunk.candidates else None
                # Unlike OpenAI, Gemini has no distinct "tool_calls" finish reason and emits a
                # function_call part whole (not fragmented across chunks) once decided - so a
                # tool call is detected directly from the part, not accumulated over time.
                tool_calls = _extract_tool_calls(candidate)
                raw_finish_reason = candidate.finish_reason if candidate and candidate.finish_reason else None
                finish_reason: FinishReason | None = None
                if tool_calls:
                    finish_reason = "tool_calls"
                elif raw_finish_reason:
                    finish_reason = _normalize_finish_reason(raw_finish_reason)
                usage = _usage_from_metadata(chunk.usage_metadata) if finish_reason else None
                delta = chunk.text or ""
                if delta or finish_reason or tool_calls:
                    yield StreamChunk(delta=delta, finish_reason=finish_reason, usage=usage, tool_calls=tool_calls)
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

    async def embed_texts(self, texts: list[str], model: str, **kwargs) -> list[list[float]]:
        config = types.EmbedContentConfig(**_translate_kwargs(kwargs)) if kwargs else None
        try:
            response = await self._client.aio.models.embed_content(
                model=model, contents=texts, config=config
            )
        except Exception as exc:
            raise ProviderError(f"Gemini embed_texts failed: {exc}") from exc
        # API guarantees results are returned in the same order as the input list.
        return [embedding.values or [] for embedding in (response.embeddings or [])]
