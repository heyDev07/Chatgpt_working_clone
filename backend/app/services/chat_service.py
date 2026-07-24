import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.definitions import DEFAULT_AGENT, get_agent
from app.config.settings import get_settings
from app.core.exceptions import NotFoundError, ProviderError
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.conversation_summary_repo import ConversationSummaryRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.message_repo import MessageRepository
from app.services.agent_coordinator import classify_agent
from app.services.memory_extraction import run_memory_extraction
from app.services.title_generation import run_title_generation
from app.tools.base import ToolResult
from app.tools.browser import PlaywrightBrowserSession
from app.tools.registry import build_playwright_tools, get_tool_registry
from app.tools.router import ToolRouter
from app.vectorstore.qdrant_client import search as search_document_chunks

logger = logging.getLogger("app.summarization")

# Chunks scored below this cosine-similarity threshold are treated as noise rather than
# genuinely relevant context and left out of the prompt.
RETRIEVAL_SCORE_THRESHOLD = 0.5
RETRIEVAL_TOP_K = 5

# Once a conversation exceeds this many messages, older ones are collapsed into a running
# summary and only the most recent RECENT_MESSAGE_COUNT are sent verbatim - keeps token usage
# from growing unbounded in long conversations. Values match the book's "10-20 messages remain
# unchanged" guidance.
SUMMARIZE_THRESHOLD = 25
RECENT_MESSAGE_COUNT = 15

# Guards against a model that keeps calling tools indefinitely without ever producing a final
# answer - five rounds is generous for any real task and cheap to hit as a hard stop.
MAX_TOOL_ITERATIONS = 5

_SUMMARY_SYSTEM_PROMPT = (
    "Summarize the following conversation concisely, preserving key facts, decisions, and "
    "context needed to continue it naturally. Write a compact narrative paragraph, not a "
    "transcript. No meta-commentary about the summary itself."
)

_FALLBACK_TITLE_LENGTH = 50


def _fallback_title(content: str) -> str:
    """Immediate placeholder title shown the instant a conversation starts, before the
    fire-and-forget AI title (see title_generation.py) replaces it - truncates on a word
    boundary with an ellipsis instead of cutting mid-word."""
    stripped = content.strip()
    if len(stripped) <= _FALLBACK_TITLE_LENGTH:
        return stripped
    truncated = stripped[:_FALLBACK_TITLE_LENGTH].rsplit(" ", 1)[0]
    return f"{truncated or stripped[:_FALLBACK_TITLE_LENGTH]}…"


class ChatService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.memories = MemoryRepository(db)
        self.summaries = ConversationSummaryRepository(db)
        self.documents = DocumentRepository(db)
        self.provider_manager = provider_manager

    async def get_authorized_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        """Must be called (and awaited) before constructing a StreamingResponse - once that
        response starts, headers/status are already committed and a 404 can no longer be sent."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        return conversation

    async def set_message_feedback(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, message_id: uuid.UUID, feedback: str | None
    ) -> Message:
        conversation = await self.get_authorized_conversation(conversation_id, user_id)
        message = await self.messages.get_by_id(message_id, conversation.id)
        if not message or message.role != "assistant":
            raise NotFoundError("Message not found")
        message = await self.messages.set_feedback(message, feedback)
        await self.db.commit()
        return message

    async def stream_message(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict]:
        # Re-fetch within this service's own session rather than accepting an ORM object
        # from the caller: this method is meant to run inside a StreamingResponse generator,
        # which is iterated *after* the route function returns - by then, a request-scoped
        # Depends(get_db) session would already be closed. See get_authorized_conversation.
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        await self.messages.create(conversation.id, role="user", content=content)
        await self.db.commit()

        history = await self.messages.list_for_conversation(conversation.id)

        if len(history) == 1 and conversation.title_is_auto:
            conversation.title = _fallback_title(content)
            await self.db.commit()
            asyncio.create_task(
                run_title_generation(
                    self.provider_manager, conversation.id, user_id, conversation.provider, conversation.model, content
                )
            )

        async for event in self._generate_and_persist(conversation, history):
            yield event

    async def regenerate(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> AsyncIterator[dict]:
        """Re-run the assistant turn for the current end of the conversation. If the last
        message is an assistant reply (the normal 'regenerate' case), it's discarded and
        replaced. If the last message is a user message with no reply (e.g. a totally failed
        attempt where nothing was ever persisted), this just generates the missing reply -
        covering both 'regenerate' and 'retry after failure' with one endpoint."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        history = await self.messages.list_for_conversation(conversation.id)
        if not history:
            yield {"event": "error", "data": {"code": "invalid_state", "message": "Nothing to regenerate"}}
            return

        if history[-1].role == "assistant":
            last_assistant = history.pop()
            await self.messages.delete(last_assistant)
            await self.db.commit()

        async for event in self._generate_and_persist(conversation, history):
            yield event

    async def edit_message(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, message_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict]:
        """Edits a previous user message and forks the conversation from that point: every
        message after it (the old reply, and anything after a since-regenerated reply) is
        discarded, then a new assistant reply is generated for the edited content."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        message = await self.messages.get_by_id(message_id, conversation.id)
        if not message or message.role != "user":
            yield {"event": "error", "data": {"code": "invalid_state", "message": "Message cannot be edited"}}
            return

        # Captured before mutating: whether this is the first message - editing it should
        # re-derive the title, same as a brand-new first message, but only if the title is
        # still auto (title_is_auto) rather than one the user set manually, which must not be
        # clobbered.
        history_before = await self.messages.list_for_conversation(conversation.id)
        is_first_message = bool(history_before) and history_before[0].id == message.id
        title_was_auto = conversation.title_is_auto

        message.content = content
        await self.messages.delete_after(conversation.id, message.created_at)
        await self.db.commit()

        if is_first_message and title_was_auto:
            conversation.title = _fallback_title(content)
            await self.db.commit()
            asyncio.create_task(
                run_title_generation(
                    self.provider_manager, conversation.id, user_id, conversation.provider, conversation.model, content
                )
            )

        history = await self.messages.list_for_conversation(conversation.id)

        async for event in self._generate_and_persist(conversation, history):
            yield event

    async def _get_effective_history(
        self, conversation: Conversation, history: list[Message]
    ) -> tuple[list[Message], str | None]:
        """Returns the messages to actually send to the provider, plus a summary of anything
        older that got collapsed out (or None if the conversation is still short enough to send
        in full). Reuses an existing summary as-is when it already covers all current "older"
        messages; only calls the LLM to refresh it when new older messages have accumulated."""
        if len(history) <= SUMMARIZE_THRESHOLD:
            return history, None

        recent = history[-RECENT_MESSAGE_COUNT:]
        older = history[:-RECENT_MESSAGE_COUNT]

        existing = await self.summaries.get(conversation.id)
        if existing and older and existing.summarized_through_message_id == older[-1].id:
            return recent, existing.summary

        provider = self.provider_manager.get_provider(conversation.provider)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in older)
        prior_note = f"Previous summary of even earlier messages:\n{existing.summary}\n\n" if existing else ""
        summarize_messages = [
            ChatMessage(role="system", content=_SUMMARY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"{prior_note}Conversation to summarize:\n{transcript}"),
        ]
        try:
            result = await provider.generate(summarize_messages, conversation.model, temperature=0.3, max_tokens=400)
            summary_text = result.message.content.strip()
            await self.summaries.upsert(conversation.id, summary_text, older[-1].id)
            await self.db.commit()
            return recent, summary_text
        except Exception:
            logger.exception("Summarization failed for conversation %s, using full history", conversation.id)
            return history, None

    async def _retrieve_document_context(
        self, user_id: uuid.UUID, query_text: str
    ) -> tuple[str | None, list[dict]]:
        """Best-effort RAG retrieval over the user's uploaded documents. Never raises - an
        embedding-provider outage or empty knowledge base should degrade to a normal chat
        reply, not break the turn. Returns (prompt text block, source citations for the
        client) or (None, []) when nothing relevant was found."""
        settings = get_settings()
        try:
            # Skip the embedding call entirely when the user has no processed documents -
            # avoids an API round-trip on every chat turn for users not using RAG at all.
            if not await self.documents.has_ready_documents(user_id):
                return None, []

            provider = self.provider_manager.get_provider(settings.embedding_provider)
            vectors = await provider.embed_texts(
                [query_text], settings.embedding_model, output_dimensionality=settings.embedding_dimensions
            )
            if not vectors or not vectors[0]:
                return None, []

            results = await search_document_chunks(user_id, vectors[0], limit=RETRIEVAL_TOP_K)
            relevant = [(payload, score) for payload, score in results if score >= RETRIEVAL_SCORE_THRESHOLD]
            if not relevant:
                return None, []

            excerpts = "\n\n".join(f"[Source: {payload['filename']}]\n{payload['text']}" for payload, _ in relevant)
            citations = [
                {"filename": payload["filename"], "document_id": payload["document_id"], "score": score}
                for payload, score in relevant
            ]
            return excerpts, citations
        except Exception:
            logger.exception("Document retrieval failed for user %s, continuing without it", user_id)
            return None, []

    async def _generate_and_persist(
        self, conversation: Conversation, history: list[Message]
    ) -> AsyncIterator[dict]:
        provider = self.provider_manager.get_provider(conversation.provider)

        effective_history, summary_text = await self._get_effective_history(conversation, history)

        chat_messages = []
        if conversation.system_prompt:
            chat_messages.append(ChatMessage(role="system", content=conversation.system_prompt))

        remembered = await self.memories.top_for_user(conversation.user_id, limit=10)
        if remembered:
            memory_lines = "\n".join(f"- {m.memory_text}" for m in remembered)
            chat_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Relevant context you remember about this user from past conversations:\n"
                        f"{memory_lines}\n"
                        "Use this naturally where relevant. Don't mention that you 'remember' "
                        "things unless it comes up naturally in conversation."
                    ),
                )
            )

        if summary_text:
            chat_messages.append(
                ChatMessage(role="system", content=f"Summary of earlier conversation:\n{summary_text}")
            )

        citations: list[dict] = []
        if history and history[-1].role == "user":
            document_context, citations = await self._retrieve_document_context(
                conversation.user_id, history[-1].content
            )
            if document_context:
                chat_messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "Relevant excerpts from the user's uploaded documents. Use them to "
                            "answer if helpful and cite the source filename when you do; if they "
                            "aren't relevant to the question, ignore them and answer normally.\n\n"
                            f"{document_context}"
                        ),
                    )
                )

        # Route to a specialized persona based on what the latest user message actually needs.
        # Best-effort: classify_agent() never raises and falls back to "general" on any failure,
        # so a coordinator hiccup degrades to the plain default assistant rather than breaking
        # the turn - same philosophy as the RAG retrieval and memory-extraction steps above.
        selected_agent = DEFAULT_AGENT
        if history and history[-1].role == "user":
            selected_agent = await classify_agent(
                self.provider_manager, conversation.provider, conversation.model, history[-1].content
            )
        agent_def = get_agent(selected_agent)
        if agent_def.system_prompt:
            chat_messages.append(ChatMessage(role="system", content=agent_def.system_prompt))
        yield {"event": "agent", "data": {"name": agent_def.name, "label": agent_def.label}}

        chat_messages.extend(ChatMessage(role=m.role, content=m.content) for m in effective_history)

        generation_kwargs = {}
        if conversation.temperature is not None:
            generation_kwargs["temperature"] = conversation.temperature
        if conversation.max_tokens is not None:
            generation_kwargs["max_tokens"] = conversation.max_tokens
        if conversation.top_p is not None:
            generation_kwargs["top_p"] = conversation.top_p

        # A fresh browser session per turn, not per call - Playwright's tools only make sense
        # against the same open tab (navigate, then click, then screenshot), so this is
        # constructed once here and shared by every browser_* tool wrapper for the whole
        # tool-calling loop below, then torn down unconditionally in the finally block.
        # Constructing it is free (no subprocess spawned yet - see PlaywrightBrowserSession);
        # merging it into every turn's registry, not just "browser" agent turns, keeps this
        # simple and relies on allowed_tools filtering (schema-build below, and enforced again
        # at call-time further down) to keep it out of other agents' reach.
        browser_session = PlaywrightBrowserSession()
        tool_registry = get_tool_registry().child_with(build_playwright_tools(browser_session))
        tool_router = ToolRouter(self.db, tool_registry)
        tool_schemas = tool_registry.list_openai_tool_schemas(allowed=agent_def.allowed_tools) or None

        full_content = ""
        finish_reason = "stop"
        usage = None
        error_message: str | None = None

        try:
            for iteration in range(MAX_TOOL_ITERATIONS):
                round_content = ""
                round_tool_calls = None
                round_finish_reason = "stop"

                async for chunk in provider.stream(
                    chat_messages, conversation.model, tools=tool_schemas, **generation_kwargs
                ):
                    if chunk.delta:
                        round_content += chunk.delta
                        yield {"event": "token", "data": {"delta": chunk.delta}}
                    if chunk.finish_reason:
                        round_finish_reason = chunk.finish_reason
                    if chunk.usage:
                        usage = chunk.usage
                    if chunk.tool_calls:
                        round_tool_calls = chunk.tool_calls

                if round_finish_reason == "tool_calls" and round_tool_calls:
                    chat_messages.append(
                        ChatMessage(role="assistant", content=round_content, tool_calls=round_tool_calls)
                    )
                    for tool_call in round_tool_calls:
                        try:
                            arguments = json.loads(tool_call.arguments or "{}")
                        except json.JSONDecodeError:
                            arguments = {}
                        yield {
                            "event": "tool_call",
                            "data": {"id": tool_call.id, "name": tool_call.name, "arguments": arguments},
                        }
                        # tool_schemas above already excludes a not-allowed tool from what the
                        # provider was offered, but a provider isn't obligated to only ever
                        # return names it was given (and a prompt-injected tool result could try
                        # to coerce one) - this is the actual enforcement boundary, checked right
                        # before anything executes, not just what's advertised.
                        if agent_def.allowed_tools is not None and tool_call.name not in agent_def.allowed_tools:
                            result = ToolResult(
                                success=False,
                                error=f"Tool '{tool_call.name}' is not available to the '{agent_def.name}' agent",
                            )
                        else:
                            result = await tool_router.call(conversation.user_id, tool_call.name, arguments)
                        yield {
                            "event": "tool_result",
                            "data": {
                                "id": tool_call.id,
                                "name": tool_call.name,
                                "success": result.success,
                                "output": result.output,
                                "error": result.error,
                            },
                        }
                        chat_messages.append(
                            ChatMessage(
                                role="tool",
                                content=json.dumps(
                                    {"result": result.output} if result.success else {"error": result.error}
                                ),
                                tool_call_id=tool_call.id,
                                name=tool_call.name,
                            )
                        )
                    continue

                full_content = round_content
                finish_reason = round_finish_reason
                break
            else:
                error_message = f"Tool call loop exceeded {MAX_TOOL_ITERATIONS} iterations without a final answer"
                finish_reason = "error"
        except ProviderError as exc:
            error_message = str(exc)
            finish_reason = "error"
        except (GeneratorExit, anyio.get_cancelled_exc_class()):
            # Client disconnected / stopped generation mid-stream. Starlette's
            # BaseHTTPMiddleware (used by our request-logging middleware) cancels the whole
            # request via a task cancellation on disconnect, not a plain GeneratorExit - so
            # both must be handled the same way here.
            finish_reason = "cancelled"
            raise
        finally:
            # Unconditional and shielded: a browser subprocess started mid-turn must be killed
            # whether the turn finished normally, errored, hit MAX_TOOL_ITERATIONS, or the client
            # disconnected - it's never allowed to outlive this request. aclose() is a no-op if
            # browser_navigate/etc. was never actually called (no subprocess was ever spawned).
            with anyio.CancelScope(shield=True):
                await browser_session.aclose()

            assistant_message = None
            if full_content:
                # The cleanup below must run even though the enclosing scope may already be
                # cancelled (client disconnect) - without shielding, these awaits would be
                # cancelled immediately too and the partial reply would never be saved.
                with anyio.CancelScope(shield=True):
                    assistant_message = await self.messages.create(
                        conversation.id,
                        role="assistant",
                        content=full_content,
                        model=conversation.model,
                        finish_reason=finish_reason,
                        token_count=usage.completion_tokens if usage else None,
                        agent=selected_agent,
                    )
                    await self.conversations.touch(conversation)
                    await self.db.commit()

        if error_message:
            yield {"event": "error", "data": {"code": "provider_error", "message": error_message}}
            return

        # Fire-and-forget: analyze this exchange for a durable memory worth keeping. Only on a
        # clean completion (not a cancelled/partial reply) - a truncated exchange is a weak
        # signal and more likely to produce a garbled extraction. Uses its own DB session (see
        # memory_extraction.py) since it outlives this request/generator.
        if assistant_message and finish_reason == "stop" and history and history[-1].role == "user":
            asyncio.create_task(
                run_memory_extraction(
                    self.provider_manager,
                    conversation.user_id,
                    conversation.provider,
                    conversation.model,
                    history[-1].content,
                    full_content,
                )
            )

        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_message.id) if assistant_message else None,
                "finish_reason": finish_reason,
                "usage": (
                    {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage
                    else None
                ),
                "citations": citations,
            },
        }
