"""Multi-agent orchestration - the actual answer to "why aren't we using a ReAct agent for
compound requests" from earlier in this project: tool_loop_graph.py's call_model/call_tools cycle
already IS ReAct, but only within one persona for one turn. A request like "give me one AI news
bullet and Python code for X" genuinely needs two different specialists (research/search-capable
general, then coding) cooperating on one turn, which single-persona classification can't do -
classify_agent() picks exactly one agent and that's what handles the whole message.

This is a Coordinator/decompose-execute-synthesize pipeline, not a general multi-agent framework:
1. decompose(): one cheap non-streamed LLM call breaks the request into 1-4 subtasks, each
   assigned to one of the existing AGENTS personas (general/coding/writing/research/analyst/
   reviewer) - no new personas invented, reusing exactly what classify_agent() already routes to
   for the single-agent path.
2. Each subtask runs through the *same* TOOL_LOOP_GRAPH every other mode uses (so a "search"-ish
   subtask can still call tavily_search, a "coding" subtask still gets its own system prompt,
   etc) - this reuses the existing ReAct loop per subtask rather than reimplementing it.
3. synthesize(): one final streamed LLM call weaves the sub-results into one coherent answer,
   which is what actually gets persisted as the turn's single assistant message - matching every
   other mode's "one turn, one assistant message" invariant rather than cluttering history with
   N sub-messages.

Deliberately opt-in (composer mode "agent"), not a replacement for classify_agent()'s existing
single-agent routing - a plain message still goes through the normal, cheaper single-agent path
unless the user explicitly asks for this.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from app.agents.definitions import AGENTS, DEFAULT_AGENT, get_agent
from app.db.database import async_session_factory
from app.models.conversation import Conversation
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.chat_service import _fallback_title
from app.services.title_generation import run_title_generation
from app.services.tool_loop_graph import TOOL_LOOP_GRAPH, ToolLoopContext, ToolLoopState
from app.tools.registry import get_tool_registry
from app.tools.router import ToolRouter

logger = logging.getLogger("app.orchestrator")

MAX_SUBTASKS = 4

_DECOMPOSE_SYSTEM_PROMPT = (
    "Break the user's request into 1 to " + str(MAX_SUBTASKS) + " ordered subtasks, each assigned "
    "to exactly one specialist from this list:\n"
    + "\n".join(f"- {a.name}: {a.description}" for a in AGENTS.values() if a.name != "browser")
    + "\n\nIf the request only genuinely needs one specialist, return a single-item list - don't "
    "invent unnecessary steps just to have more than one. Each subtask's 'task' should be a "
    "concise, self-contained instruction for that specialist alone - it won't see the other "
    "subtasks or the original message, only what you write here.\n\n"
    'Respond with ONLY a JSON array, nothing else: [{"agent": "...", "task": "..."}, ...]'
)

_SYNTHESIZE_SYSTEM_PROMPT = (
    "You are combining the results of several specialist sub-tasks into one coherent final reply "
    "to the user's original request. Weave them together naturally - don't just concatenate them "
    "with headers, and don't mention that this was done by multiple specialists or subtasks "
    "unless the user's own request was about that process itself."
)


def _parse_steps(raw: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list) or not parsed:
        return []
    steps = []
    for item in parsed[:MAX_SUBTASKS]:
        if not isinstance(item, dict):
            continue
        agent = item.get("agent")
        task = item.get("task")
        if not isinstance(agent, str) or not isinstance(task, str) or not task.strip():
            continue
        # Same graceful-degradation as get_agent() - an unrecognized name (or "browser", excluded
        # from the prompt above since a sub-agent has no conversation-scoped browser session to
        # share) falls back to general rather than failing the whole plan.
        steps.append({"agent": agent if agent in AGENTS and agent != "browser" else DEFAULT_AGENT, "task": task.strip()})
    return steps


async def _run_subtask(provider_manager: ProviderManager, conversation: Conversation, agent_name: str, task: str) -> AsyncIterator[dict]:
    """Runs one subtask through the same TOOL_LOOP_GRAPH every other mode uses, yielding its
    token/tool_call/tool_result events live (so the user sees real progress per subtask, not a
    silent wait) and finally an internal-only 'subtask_result' the caller collects and strips
    before anything reaches the client - see stream_orchestrated below."""
    agent_def = get_agent(agent_name)
    provider = provider_manager.get_provider(conversation.provider)

    async with async_session_factory() as db:
        tool_registry = get_tool_registry()
        tool_router = ToolRouter(db, tool_registry)
        tool_schemas = tool_registry.list_openai_tool_schemas(allowed=agent_def.allowed_tools) or None

        chat_messages = []
        if agent_def.system_prompt:
            chat_messages.append(ChatMessage(role="system", content=agent_def.system_prompt))
        chat_messages.append(ChatMessage(role="user", content=task))

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
            "generation_kwargs": {},
        }

        full_content = ""
        async for stream_mode, chunk in TOOL_LOOP_GRAPH.astream(
            initial_state, config={"configurable": graph_context}, stream_mode=["custom", "values"]
        ):
            if stream_mode == "custom":
                yield chunk
            else:
                full_content = chunk["full_content"]

    yield {"event": "subtask_result", "data": {"agent": agent_name, "task": task, "result": full_content}}


async def stream_orchestrated(
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
            max_tokens=500,
        )
        steps = _parse_steps(decompose_result.message.content)
    except Exception:
        logger.exception("Orchestrator decompose step failed")
        steps = []

    # Same fallback philosophy as classify_agent() - a broken/empty decomposition degrades to a
    # single general-agent step with the original message, not a failed turn.
    if not steps:
        steps = [{"agent": DEFAULT_AGENT, "task": content}]

    yield {"event": "plan", "data": {"steps": steps}}

    sub_results: list[dict[str, str]] = []
    for step in steps:
        agent_def = get_agent(step["agent"])
        yield {"event": "agent", "data": {"name": agent_def.name, "label": agent_def.label}}
        async for event in _run_subtask(provider_manager, conversation, step["agent"], step["task"]):
            if event["event"] == "subtask_result":
                sub_results.append(event["data"])
            else:
                yield event

    yield {"event": "agent", "data": {"name": "general", "label": "Combining results"}}
    synthesis_input = "\n\n".join(
        f"[{get_agent(r['agent']).label} subtask: {r['task']}]\n{r['result']}" for r in sub_results
    )
    full_content = ""
    finish_reason = "stop"
    async for chunk in provider.stream(
        [
            ChatMessage(role="system", content=_SYNTHESIZE_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Original request: {content}\n\nSubtask results:\n{synthesis_input}",
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
        conversation.id, role="assistant", content=full_content, finish_reason=finish_reason, agent="orchestrator"
    )
    await conversations.touch(conversation)
    await db.commit()

    yield {
        "event": "done",
        "data": {"message_id": str(assistant_message.id), "finish_reason": finish_reason, "usage": None, "citations": []},
    }
