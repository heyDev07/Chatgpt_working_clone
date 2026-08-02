"""Deep Research mode: decompose a question into a few independently-researchable
sub-questions, research each one (real web search + full-page extraction, not snippets alone),
and synthesize a long, properly-cited report - the pattern behind OpenAI/Perplexity/Gemini's
"Research" features.

Structurally this is orchestrator_service.py's decompose-execute-synthesize pipeline again, reused
rather than reimplemented (same _run_subtask, same TOOL_LOOP_GRAPH underneath, same sequential
for-loop over steps) - but specialized in three ways:

1. Decompose breaks the question into research sub-questions, not "which specialist" - every
   subtask here always researches, it's the angle that varies, not the persona.
2. The research persona (_RESEARCH_AGENT below) is deliberately a local AgentDefinition, never
   registered in the global AGENTS dict. Unlike job_application, this persona's tools alone
   (search + extract) don't make a normal chat turn "Deep Research" - the multi-step pipeline IS
   the feature. Registering it globally would let classify_agent()'s classifier (built from
   AGENTS.values() at import time) silently route an ordinary chat message into a single-turn,
   non-multi-step stand-in for it - not broken, just a confusing, underwhelming impostor of what
   "Deep Research" actually means. Keeping it local makes that impossible by construction.
3. Sub-task tool_result events are inspected as they stream through (forwarded to the client
   unchanged either way) to harvest real citations from tavily_search/tavily_extract output -
   deduped by URL - which the synthesis step is given as a numbered source list and told to cite
   with [n] markers, and which get persisted on the final message (see Message.citations).

Sequential by design, same as the orchestrator - not asyncio.gather. This is what makes "respect
a free-tier LLM rate limit" close to free rather than something to build: bursting several
concurrent sub-question calls against a free-tier per-minute cap would be the wrong shape
regardless of citations, and the orchestrator's existing for-loop already avoids it.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from app.agents.definitions import AgentDefinition
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.chat_service import _fallback_title
from app.services.orchestrator_service import _run_subtask
from app.services.title_generation import run_title_generation

logger = logging.getLogger("app.research")

# Tighter than the orchestrator's 4 - each research subtask itself does multiple search/extract
# tool round-trips (unlike a typical orchestrator subtask, which is often a single call), so the
# total LLM-call volume per sub-question is already higher.
MAX_SUBQUESTIONS = 3

_RESEARCH_AGENT = AgentDefinition(
    name="deep_research",
    label="Researching",
    description="Deep multi-source web research producing a long, cited report.",
    system_prompt=(
        "You are researching one specific sub-question as part of a larger research report. Use "
        "tavily_search to find relevant, credible sources, and tavily_extract to pull the full "
        "content of the most promising results rather than relying on search snippets alone. "
        "Write a thorough, factual answer to your sub-question grounded only in what you actually "
        "found - note where sources disagree or where you couldn't find a clear answer, rather "
        "than guessing or filling gaps from your own training data."
    ),
    allowed_tools=frozenset({"tavily_search", "tavily_extract"}),
)

_DECOMPOSE_SYSTEM_PROMPT = (
    f"Break the user's research question into 1 to {MAX_SUBQUESTIONS} concrete, "
    "independently-answerable research sub-questions that together would let you write a "
    "thorough report. Each sub-question must stand alone - whoever researches it won't see the "
    "others, only what you write here. If the question is narrow enough to need just one "
    "sub-question, return a single-item list rather than inventing extra ones.\n\n"
    'Respond with ONLY a JSON array, nothing else: [{"question": "..."}, ...]'
)

_SYNTHESIZE_SYSTEM_PROMPT = (
    "You are writing a long, well-structured research report from the findings below, which come "
    "from several sub-questions that have already been researched, plus a numbered list of the "
    "sources those findings actually came from. Write in markdown with clear headings. Cite "
    "claims using [n] markers that match the numbered source list exactly - only cite a source "
    "that's actually in that list, never invent a citation or a number that isn't there. If the "
    "findings disagree or leave something uncertain, say so rather than papering over it."
)


def _parse_subquestions(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list) or not parsed:
        return []
    questions: list[str] = []
    for item in parsed[:MAX_SUBQUESTIONS]:
        question = item.get("question") if isinstance(item, dict) else item if isinstance(item, str) else None
        if isinstance(question, str) and question.strip():
            questions.append(question.strip())
    return questions


def _harvest_citations(event: dict, citations: list[dict], seen_urls: set[str]) -> None:
    """Inspects a tool_result event for tavily_search/tavily_extract output and appends any new
    (deduped by URL) sources found in it. Never raises - a malformed or unexpected tool output
    shape should just contribute no citations, not break the research turn."""
    if event.get("event") != "tool_result":
        return
    data = event.get("data") or {}
    if data.get("name") not in ("tavily_search", "tavily_extract") or not data.get("success"):
        return
    output = data.get("output")
    if not isinstance(output, str):
        return
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        return
    for result in results:
        if not isinstance(result, dict):
            continue
        url = result.get("url")
        if not isinstance(url, str) or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = result.get("title") or url
        snippet = (result.get("content") or result.get("raw_content") or "")[:300]
        citations.append({"title": title, "url": url, "snippet": snippet})


async def stream_research(
    db, provider_manager: ProviderManager, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str
) -> AsyncIterator[dict]:
    conversations = ConversationRepository(db)
    messages = MessageRepository(db)

    conversation = await conversations.get_for_user(conversation_id, user_id)
    if not conversation:
        yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
        return

    await messages.create(conversation.id, role="user", content=content)
    await db.commit()

    history = await messages.list_for_conversation(conversation.id)
    if len(history) == 1 and conversation.title_is_auto:
        conversation.title = _fallback_title(content)
        await db.commit()
        asyncio.create_task(
            run_title_generation(
                provider_manager, conversation.id, user_id, conversation.provider, conversation.model, content
            )
        )

    provider = provider_manager.get_provider(conversation.provider)

    try:
        decompose_result = await provider.generate(
            [
                ChatMessage(role="system", content=_DECOMPOSE_SYSTEM_PROMPT),
                ChatMessage(role="user", content=content),
            ],
            conversation.model,
            temperature=0.0,
            max_tokens=400,
        )
        questions = _parse_subquestions(decompose_result.message.content)
    except Exception:
        logger.exception("Research decompose step failed")
        questions = []

    # Same fallback philosophy as classify_agent()/orchestrator's own decompose - a broken/empty
    # decomposition degrades to a single research pass over the original question, not a failed turn.
    if not questions:
        questions = [content]

    steps = [{"agent": _RESEARCH_AGENT.name, "task": question} for question in questions]
    yield {"event": "plan", "data": {"steps": steps}}

    sub_results: list[dict[str, str]] = []
    citations: list[dict] = []
    seen_urls: set[str] = set()
    for step in steps:
        yield {"event": "agent", "data": {"name": _RESEARCH_AGENT.name, "label": _RESEARCH_AGENT.label}}
        async for event in _run_subtask(provider_manager, conversation, _RESEARCH_AGENT, step["task"]):
            if event["event"] == "subtask_result":
                sub_results.append(event["data"])
            else:
                _harvest_citations(event, citations, seen_urls)
                yield event

    yield {"event": "agent", "data": {"name": "general", "label": "Writing report"}}

    source_list = (
        "\n".join(f"[{i + 1}] {c['title']} - {c['url']}" for i, c in enumerate(citations))
        if citations
        else "(no sources were found)"
    )
    findings = "\n\n".join(f"[Sub-question: {r['task']}]\n{r['result']}" for r in sub_results)

    full_content = ""
    finish_reason = "stop"
    async for chunk in provider.stream(
        [
            ChatMessage(role="system", content=_SYNTHESIZE_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"Original research question: {content}\n\n"
                    f"Findings from sub-questions:\n{findings}\n\n"
                    f"Numbered sources (cite these with [n], never a number not listed here):\n{source_list}"
                ),
            ),
        ],
        conversation.model,
    ):
        if chunk.delta:
            full_content += chunk.delta
            yield {"event": "token", "data": {"delta": chunk.delta}}
        if chunk.finish_reason:
            finish_reason = chunk.finish_reason

    assistant_message = await messages.create(
        conversation.id,
        role="assistant",
        content=full_content,
        finish_reason=finish_reason,
        agent="deep_research",
        citations=citations or None,
    )
    await conversations.touch(conversation)
    await db.commit()

    yield {
        "event": "done",
        "data": {
            "message_id": str(assistant_message.id),
            "finish_reason": finish_reason,
            "usage": None,
            "citations": citations,
        },
    }
