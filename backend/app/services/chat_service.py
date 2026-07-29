import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.definitions import DEFAULT_AGENT, get_agent
from app.config.settings import get_settings
from app.core.exceptions import NotFoundError, ProviderError
from app.core.metrics import llm_request_duration_seconds, llm_requests_total, llm_tokens_total
from app.db.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base_provider import ChatMessage, ImagePart
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.conversation_summary_repo import ConversationSummaryRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.message_attachment_repo import MessageAttachmentRepository
from app.repositories.message_repo import MessageRepository
from app.services.agent_coordinator import classify_agent
from app.services.memory_extraction import run_memory_extraction
from app.services.title_generation import run_title_generation
from app.services.tool_loop_graph import TOOL_LOOP_GRAPH, ToolLoopContext, ToolLoopState
from app.storage.s3_client import download_bytes
from app.tools.browser import PlaywrightBrowserSession
from app.tools.contacts import ListContactsTool, UpsertContactTool
from app.tools.google_workspace import (
    CreateCalendarEventTool,
    ListCalendarEventsTool,
    SearchGmailTool,
    SendGmailTool,
)
from app.tools.registry import build_playwright_tools, get_tool_registry
from app.tools.reminders import CreateReminderTool
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

_SUMMARY_SYSTEM_PROMPT = (
    "Summarize the following conversation concisely, preserving key facts, decisions, and "
    "context needed to continue it naturally. Write a compact narrative paragraph, not a "
    "transcript. No meta-commentary about the summary itself."
)

_FALLBACK_TITLE_LENGTH = 50

# In-flight background generations (see ChatService._stream_resilient), keyed by conversation id.
# Two jobs: (1) a strong reference so asyncio doesn't garbage-collect a task nothing else holds
# onto - it only keeps a weak reference internally, and a task can be silently destroyed mid-run
# otherwise, defeating the entire point of surviving after the request that spawned it goes away;
# (2) a lookup so an explicit "Stop generating" click (see stop_generation below) can find and
# cancel the right task - deliberately different from a client disconnect, which must NOT cancel
# it. Each task removes its own entry once done via add_done_callback, guarded by identity so a
# newer generation for the same conversation started after this one finished can't be evicted by
# a late-firing callback from the one it replaced.
_background_generation_tasks: dict[uuid.UUID, asyncio.Task] = {}


def _fallback_title(content: str) -> str:
    """Immediate placeholder title shown the instant a conversation starts, before the
    fire-and-forget AI title (see title_generation.py) replaces it - truncates on a word
    boundary with an ellipsis instead of cutting mid-word."""
    stripped = content.strip()
    if not stripped:
        return "Image"  # an image-only message (no caption) has no text to derive a title from
    if len(stripped) <= _FALLBACK_TITLE_LENGTH:
        return stripped
    truncated = stripped[:_FALLBACK_TITLE_LENGTH].rsplit(" ", 1)[0]
    return f"{truncated or stripped[:_FALLBACK_TITLE_LENGTH]}…"


# Tavily result "content" fields are often several paragraphs of scraped page text (see the
# tavily_search tool's own output) - a snippet this long, not the full thing, is what makes the
# formatted message actually scannable rather than a wall of text for every one of up to 5
# results.
_SEARCH_SNIPPET_LENGTH = 280


def _format_search_results(query: str, raw_output: str) -> str:
    """Turns tavily_search's raw JSON string output into a readable markdown message - this is
    the entire "answer," there is no LLM synthesis step in search mode by design (see
    stream_search's docstring). Falls back to showing the raw output verbatim if it isn't the
    shape expected (Tavily's response format is out of this app's control), rather than raising
    and losing the search results entirely."""
    try:
        data = json.loads(raw_output)
        results = data.get("results", [])
    except (json.JSONDecodeError, AttributeError):
        return raw_output

    if not results:
        return f"No web results found for \"{query}\"."

    lines = [f"**Web search results for \"{query}\":**\n"]
    for result in results:
        title = result.get("title") or result.get("url", "Untitled")
        url = result.get("url", "")
        content = (result.get("content") or "").strip().replace("\n", " ")
        snippet = content[:_SEARCH_SNIPPET_LENGTH] + ("…" if len(content) > _SEARCH_SNIPPET_LENGTH else "")
        lines.append(f"**[{title}]({url})**\n{snippet}\n")
    return "\n".join(lines)


class ChatService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.memories = MemoryRepository(db)
        self.summaries = ConversationSummaryRepository(db)
        self.documents = DocumentRepository(db)
        self.attachments = MessageAttachmentRepository(db)
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
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        attachment_ids: list[uuid.UUID] | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[dict]:
        # Re-fetch within this service's own session rather than accepting an ORM object
        # from the caller: this method is meant to run inside a StreamingResponse generator,
        # which is iterated *after* the route function returns - by then, a request-scoped
        # Depends(get_db) session would already be closed. See get_authorized_conversation.
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        message = await self.messages.create(conversation.id, role="user", content=content)
        if attachment_ids:
            await self.attachments.attach_to_message(attachment_ids, message.id, user_id)
        await self.db.commit()

        history = await self.messages.list_for_conversation(conversation.id)

        if len(history) == 1 and conversation.title_is_auto:
            conversation.title = _fallback_title(content)
            await self.db.commit()
            if content.strip():  # nothing to title-generate from an image-only message
                asyncio.create_task(
                    run_title_generation(
                        self.provider_manager, conversation.id, user_id, conversation.provider, conversation.model, content
                    )
                )

        async for event in self._stream_resilient(conversation.id, user_id, agent):
            yield event

    async def stream_search(self, conversation_id: uuid.UUID, user_id: uuid.UUID, query: str) -> AsyncIterator[dict]:
        """Explicit web-search mode: added alongside stream_message, not in place of it - the
        model still decides for itself whether to call tavily_search during a normal turn, and
        that path is completely untouched. This one exists for the opposite case: the user
        explicitly wants a direct web search with no LLM involved at all, most importantly
        because it still works when every configured provider's quota is exhausted (confirmed
        live, repeatedly, this session) - the automatic path can't help you then since even
        deciding *whether* to search is itself an LLM call. This method never calls a provider,
        by design, not merely by accident of not needing to."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        await self.messages.create(conversation.id, role="user", content=query)
        await self.db.commit()

        history = await self.messages.list_for_conversation(conversation.id)
        if len(history) == 1 and conversation.title_is_auto:
            conversation.title = _fallback_title(query)
            await self.db.commit()

        yield {"event": "agent", "data": {"name": "web_search", "label": "Web Search"}}

        tool_router = ToolRouter(self.db, get_tool_registry())
        full_content = ""
        finish_reason = "stop"
        error_message: str | None = None
        try:
            result = await tool_router.call(user_id, "tavily_search", {"query": query})
            if not result.success:
                error_message = result.error or "Web search failed"
                finish_reason = "error"
            else:
                full_content = _format_search_results(query, result.output)
                yield {"event": "token", "data": {"delta": full_content}}
        except (GeneratorExit, anyio.get_cancelled_exc_class()):
            finish_reason = "cancelled"
            raise
        finally:
            assistant_message = None
            if full_content:
                with anyio.CancelScope(shield=True):
                    assistant_message = await self.messages.create(
                        conversation.id, role="assistant", content=full_content, finish_reason=finish_reason,
                        agent="web_search",
                    )
                    await self.conversations.touch(conversation)
                    await self.db.commit()

        if error_message:
            yield {"event": "error", "data": {"code": "tool_error", "message": error_message}}
            return

        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_message.id) if assistant_message else None,
                "finish_reason": finish_reason,
                "usage": None,
                "citations": [],
            },
        }

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

        async for event in self._stream_resilient(conversation.id, user_id):
            yield event

    async def edit_message(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
        content: str,
        attachment_ids: list[uuid.UUID] | None = None,
        agent: str | None = None,
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
        if attachment_ids:
            await self.attachments.attach_to_message(attachment_ids, message.id, user_id)
        await self.messages.delete_after(conversation.id, message.created_at)
        await self.db.commit()

        if is_first_message and title_was_auto:
            conversation.title = _fallback_title(content)
            await self.db.commit()
            if content.strip():
                asyncio.create_task(
                    run_title_generation(
                        self.provider_manager, conversation.id, user_id, conversation.provider, conversation.model, content
                    )
                )

        async for event in self._stream_resilient(conversation.id, user_id, agent):
            yield event

    async def _stream_resilient(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, forced_agent: str | None = None
    ) -> AsyncIterator[dict]:
        """Runs the actual generation (_generate_and_persist) in a background asyncio task on
        its own DB session, independent of the request that's consuming this generator - so a
        client disconnect (tab closed, page refreshed, user switches conversations) stops this
        generator from yielding further SSE events, but does NOT cancel the underlying
        generation or its persistence, the same way a real chat product's response keeps being
        produced and saved even if you navigate away mid-stream. Confirmed live this was a real
        bug before this existed: killing the client connection mid-turn left nothing but the
        user's own message persisted - the assistant's reply was silently discarded entirely.

        The caller's own session (self.db) can't be reused for the background task: it's opened
        per-request inside the route's event_stream() generator (see messages.py) and torn down
        when THAT generator's task is cancelled - exactly the thing this needs to survive. A
        fresh session + fresh ChatService is opened here instead, mirroring the same pattern
        title_generation.py/memory_extraction.py already use for their own fire-and-forget work.
        conversation_id/user_id (plain UUIDs, not ORM objects) are what's passed in rather than
        the caller's own `conversation`/`history` objects, since those are bound to the caller's
        session and aren't safe to touch from a different one - the background task re-fetches
        both fresh against its own session instead."""
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def produce() -> None:
            try:
                async with async_session_factory() as db:
                    service = ChatService(db, self.provider_manager)
                    conversation = await service.conversations.get_for_user(conversation_id, user_id)
                    if conversation is None:
                        return
                    history = await service.messages.list_for_conversation(conversation.id)
                    async for event in service._generate_and_persist(conversation, history, forced_agent):
                        await queue.put(event)
            except Exception:
                logger.exception("Background generation failed for conversation %s", conversation_id)
            finally:
                await queue.put(None)  # sentinel: no more events, whether from success or failure

        task = asyncio.create_task(produce())
        _background_generation_tasks[conversation_id] = task
        task.add_done_callback(
            lambda t: _background_generation_tasks.pop(conversation_id, None)
            if _background_generation_tasks.get(conversation_id) is t
            else None
        )

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    async def stop_generation(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Explicit user action ("Stop generating"), unlike a client disconnect - deliberately
        cancels the in-flight background task rather than letting it keep running. Cancelling
        lands inside _generate_and_persist's own except/finally (the same path a real disconnect
        used to take before _stream_resilient existed): the shielded finally block still runs,
        so any already-completed content is preserved, but the loop stops making further
        provider calls rather than running to completion invisibly. Returns whether a live
        generation was actually found and cancelled - authorization is implicit in
        conversation_id having come from this user's own SSE connection in the first place, but
        this is a separate route/request, so ownership is still verified here rather than
        trusting the id alone."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")

        task = _background_generation_tasks.get(conversation_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _to_chat_message(self, message: Message) -> ChatMessage:
        """Fetches attached image bytes from S3 for a history message, if it has any - called
        only for messages already within effective_history's verbatim window (RECENT_MESSAGE_
        COUNT), which already bounds how many messages, and therefore how many image downloads,
        a single turn can incur. Older, summarized-away messages never reach this - their images
        (like their text) are lost to the summary, same tradeoff the text already makes."""
        images = None
        if message.attachments:
            images = [
                ImagePart(data=await download_bytes(a.storage_key), mime_type=a.content_type)
                for a in message.attachments
            ]
        return ChatMessage(role=message.role, content=message.content, images=images)

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
        self, conversation: Conversation, history: list[Message], forced_agent: str | None = None
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
        # forced_agent skips the classifier entirely - an explicit Code/Write mode toggle in the
        # composer, not the model's own guess. get_agent() falls back to "general" for an
        # unrecognized name either way, so an invalid forced_agent degrades the same way a
        # classifier miss would, rather than needing its own validation here.
        if forced_agent:
            selected_agent = forced_agent
        else:
            selected_agent = DEFAULT_AGENT
            if history and history[-1].role == "user":
                selected_agent = await classify_agent(
                    self.provider_manager, conversation.provider, conversation.model, history[-1].content
                )
        agent_def = get_agent(selected_agent)
        if agent_def.system_prompt:
            chat_messages.append(ChatMessage(role="system", content=agent_def.system_prompt))
        yield {"event": "agent", "data": {"name": agent_def.name, "label": agent_def.label}}

        for m in effective_history:
            chat_messages.append(await self._to_chat_message(m))

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
        # Merged into the registry ONLY for the "browser" agent - allowed_tools=None on every
        # other agent means "no restriction", not "restricted to non-browser tools", so merging
        # unconditionally would silently make every browser_* tool (including
        # browser_file_upload, which can read arbitrary files within the server's working
        # directory - see PLAYWRIGHT_ARGS' cwd) reachable from "general"/"coding"/etc too,
        # defeating the entire point of a dedicated scoped persona.
        # create_reminder/upsert_contact/list_contacts/Gmail/Calendar tools are request-scoped
        # (need this turn's user_id, which the model can't be trusted to supply itself as a plain
        # argument) - merged into every turn's registry unconditionally, unlike browser_* tools
        # below, since these are general requests any persona might reasonably get, not specific
        # to one agent. The Gmail/Calendar tools fail gracefully with a clear "not connected"
        # error from get_valid_access_token if the user hasn't done the OAuth flow in Settings -
        # no need to conditionally merge them only for users who have.
        tool_registry = get_tool_registry().child_with(
            [
                CreateReminderTool(conversation.user_id, conversation.id),
                UpsertContactTool(conversation.user_id),
                ListContactsTool(conversation.user_id),
                SearchGmailTool(conversation.user_id),
                ListCalendarEventsTool(conversation.user_id),
                SendGmailTool(conversation.user_id),
                CreateCalendarEventTool(conversation.user_id),
            ]
        )
        browser_session: PlaywrightBrowserSession | None = None
        if selected_agent == "browser":
            browser_session = PlaywrightBrowserSession()
            # Eagerly opened here rather than lazily on first tool call, so a browser-persona
            # turn that never actually calls a browser_* tool still fails fast on a broken
            # Playwright MCP subprocess instead of silently proceeding. See
            # PlaywrightBrowserSession's docstring for why open()/call_tool()/aclose() are safe
            # to call from different tasks at all (they aren't, without its internal worker-task
            # design) - relevant now that the tool loop below runs as a LangGraph graph, whose
            # nodes execute via their own asyncio.create_task() calls.
            await browser_session.open()
            tool_registry = tool_registry.child_with(build_playwright_tools(browser_session))
        tool_router = ToolRouter(self.db, tool_registry)
        tool_schemas = tool_registry.list_openai_tool_schemas(allowed=agent_def.allowed_tools) or None

        # Applies regardless of which persona was picked above - "general" (the default agent
        # for most everyday questions, including exactly the kind of "who currently holds X"
        # factual question this was written for) has an empty system_prompt otherwise, so
        # nothing was ever telling the model its training data goes stale. Without this, a model
        # answers confidently and wrong from memory rather than reaching for tavily_search, even
        # though the tool is available to it - a real bug (confirmed live: "who is the education
        # minister of India" got an outdated name) fixed here rather than by trying to get every
        # individual agent's persona prompt to remember to say this. Gated on tavily_search
        # actually being offered this turn - telling the model to use a tool that isn't in its
        # tool list (no TAVILY_API_KEY configured, or a persona that excludes it) would just be a
        # confusing, unactionable instruction.
        if tool_schemas and any(t["function"]["name"] == "tavily_search" for t in tool_schemas):
            chat_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Your training data has a cutoff date. Facts that can change over time - "
                        "who currently holds a position or office, ongoing events, recent news, "
                        "current prices or software versions - may be outdated in your memory "
                        "even when you feel confident about them. When a question depends on "
                        "something that could have changed, use the tavily_search tool to verify "
                        "current information rather than answering from memory alone."
                    ),
                )
            )

        full_content = ""
        finish_reason = "stop"
        usage = None
        error_message: str | None = None
        turn_started = time.monotonic()
        # generate_image already stores its bytes in S3 during the tool call itself (it has no
        # DB access - see image_generation.py) - this just accumulates what it reported so the
        # resulting MessageAttachment rows can be created once the assistant message they belong
        # to actually exists, in the finally block below.
        generated_attachments: list[dict] = []

        # The actual model-call / tool-execution cycle, as a LangGraph graph (see
        # tool_loop_graph.py for why just this part and not the rest of the turn). No
        # checkpointer - each call below is one self-contained run; "custom" stream chunks are
        # the exact SSE event dicts to forward to the client unchanged, "values" chunks are the
        # full accumulated graph state, of which only the last one (once the graph reaches END)
        # actually matters here.
        initial_state: ToolLoopState = {
            "chat_messages": chat_messages,
            "iteration": 0,
            "full_content": "",
            "finish_reason": "stop",
            "usage": None,
            "generated_attachments": [],
            "error_message": None,
            "round_tool_calls": None,
        }
        graph_context: ToolLoopContext = {
            "provider": provider,
            "model": conversation.model,
            "tool_schemas": tool_schemas,
            "agent_def": agent_def,
            "tool_router": tool_router,
            "user_id": conversation.user_id,
            "generation_kwargs": generation_kwargs,
        }

        try:
            async for stream_mode, chunk in TOOL_LOOP_GRAPH.astream(
                initial_state, config={"configurable": graph_context}, stream_mode=["custom", "values"]
            ):
                if stream_mode == "custom":
                    yield chunk
                else:
                    full_content = chunk["full_content"]
                    finish_reason = chunk["finish_reason"]
                    usage = chunk["usage"]
                    generated_attachments = chunk["generated_attachments"]
                    error_message = chunk["error_message"]
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
            if browser_session is not None:
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
                    for generated in generated_attachments:
                        storage_key = generated.get("storage_key")
                        if not storage_key:
                            continue  # malformed tool output - image bytes never got stored
                        await self.attachments.create_for_message(
                            user_id=conversation.user_id,
                            message_id=assistant_message.id,
                            filename=generated.get("filename", "generated-image.jpg"),
                            content_type=generated.get("content_type", "image/jpeg"),
                            size_bytes=generated.get("size_bytes", 0),
                            storage_key=storage_key,
                        )
                    await self.conversations.touch(conversation)
                    await self.db.commit()

            # Recorded regardless of outcome (including "error"/"cancelled" finish_reasons, when
            # full_content was empty and nothing above even ran) - an operator watching this
            # metric needs to see failed turns, not just successful ones.
            llm_requests_total.labels(
                provider=conversation.provider, model=conversation.model, finish_reason=finish_reason
            ).inc()
            llm_request_duration_seconds.labels(provider=conversation.provider, model=conversation.model).observe(
                time.monotonic() - turn_started
            )
            if usage:
                llm_tokens_total.labels(provider=conversation.provider, model=conversation.model).inc(
                    usage.completion_tokens
                )

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
