"""LangGraph implementation of the tool-calling loop - the one part of a chat turn that's
actually graph-shaped: a real cycle (call the model, maybe call tools, call the model again)
with a conditional exit. RAG retrieval, memory injection, and summarization in chat_service.py
stay as plain async functions rather than graph nodes - they're one-shot linear steps with no
branching, and forcing them into a graph would just be ceremony around code that's already
correct and already tested.

No checkpointer: each turn compiles into one graph run and nothing about it needs to survive
past the request - chat_service.py already persists the final assistant message itself once the
graph finishes (in its own shielded finally block), so adding LangGraph-level persistence here
would just be a second, redundant durability mechanism for the same data.

Streaming: SSE token/tool_call/tool_result events are emitted from inside the nodes via
get_stream_writer() (LangGraph's "custom" stream mode), using the exact same
{"event": ..., "data": ...} shape chat_service.py already yields to the client. Swapping the
loop's internals for a graph doesn't change the wire protocol the frontend already handles.

Node functions MUST type their `config` parameter as RunnableConfig, not plain dict - LangGraph
inspects the annotation to decide whether to inject it at all; a plain `dict` annotation makes it
silently skip injection, surfacing as "missing 1 required positional argument: 'config'" at
runtime rather than at graph-build time. Confirmed by testing both directly before wiring this
in, not assumed from documentation.
"""

import json
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from app.agents.definitions import AgentDefinition
from app.providers.base_provider import BaseProvider, ChatMessage, ToolCall, Usage
from app.services.tool_confirmation import await_confirmation
from app.tools.base import ToolResult
from app.tools.router import ToolRouter

# Guards against a model that keeps calling tools indefinitely without ever producing a final
# answer - five rounds is generous for any real task and cheap to hit as a hard stop. Enforced
# manually in call_model_node (not via LangGraph's own recursion_limit) so the resulting error
# message/finish_reason exactly match what chat_service.py produced before this was a graph.
MAX_TOOL_ITERATIONS = 5


class ToolLoopState(TypedDict):
    chat_messages: list[ChatMessage]
    iteration: int
    full_content: str
    finish_reason: str
    usage: Usage | None
    generated_attachments: list[dict]
    error_message: str | None
    round_tool_calls: list[ToolCall] | None


class ToolLoopContext(TypedDict):
    """Per-turn dependencies that don't change as the graph runs - service objects and request
    context, not state. Passed via config["configurable"] instead of being threaded through
    every node's state dict, which is for data that evolves across steps, not fixed context."""

    provider: BaseProvider
    model: str
    tool_schemas: list[dict] | None
    agent_def: AgentDefinition
    tool_router: ToolRouter
    user_id: Any
    generation_kwargs: dict


async def call_model_node(state: ToolLoopState, config: RunnableConfig) -> dict:
    ctx: ToolLoopContext = config["configurable"]
    writer = get_stream_writer()

    if state["iteration"] >= MAX_TOOL_ITERATIONS:
        return {
            "finish_reason": "error",
            "error_message": f"Tool call loop exceeded {MAX_TOOL_ITERATIONS} iterations without a final answer",
        }

    round_content = ""
    round_tool_calls: list[ToolCall] | None = None
    round_finish_reason = "stop"
    usage = state["usage"]

    async for chunk in ctx["provider"].stream(
        state["chat_messages"], ctx["model"], tools=ctx["tool_schemas"], **ctx["generation_kwargs"]
    ):
        if chunk.delta:
            round_content += chunk.delta
            writer({"event": "token", "data": {"delta": chunk.delta}})
        if chunk.finish_reason:
            round_finish_reason = chunk.finish_reason
        if chunk.usage:
            usage = chunk.usage
        if chunk.tool_calls:
            round_tool_calls = chunk.tool_calls

    updates: dict = {
        "iteration": state["iteration"] + 1,
        "usage": usage,
        "finish_reason": round_finish_reason,
        "round_tool_calls": round_tool_calls,
    }
    if round_finish_reason == "tool_calls" and round_tool_calls:
        updates["chat_messages"] = [
            *state["chat_messages"],
            ChatMessage(role="assistant", content=round_content, tool_calls=round_tool_calls),
        ]
    else:
        updates["full_content"] = round_content
    return updates


async def call_tools_node(state: ToolLoopState, config: RunnableConfig) -> dict:
    ctx: ToolLoopContext = config["configurable"]
    agent_def = ctx["agent_def"]
    writer = get_stream_writer()

    chat_messages = list(state["chat_messages"])
    generated_attachments = list(state["generated_attachments"])

    for tool_call in state["round_tool_calls"] or []:
        try:
            arguments = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        writer({"event": "tool_call", "data": {"id": tool_call.id, "name": tool_call.name, "arguments": arguments}})

        # tool_schemas already excludes a not-allowed tool from what the provider was offered,
        # but a provider isn't obligated to only ever return names it was given (and a
        # prompt-injected tool result could try to coerce one) - this is the actual enforcement
        # boundary, checked right before anything executes, not just what's advertised.
        if agent_def.allowed_tools is not None and tool_call.name not in agent_def.allowed_tools:
            result = ToolResult(
                success=False, error=f"Tool '{tool_call.name}' is not available to the '{agent_def.name}' agent"
            )
        else:
            registered_tool = ctx["tool_router"].registry.get(tool_call.name)
            needs_confirmation = (
                registered_tool is not None and registered_tool.definition.permission_level == "restricted"
            )
            if needs_confirmation:
                # Pauses this turn's background task (see await_confirmation's docstring) until
                # the frontend's Approve/Reject action resolves it from a separate request, or it
                # times out - either way the model always gets a real tool-role result back, never
                # left hanging, so it can react ("okay, I won't send that") instead of erroring.
                writer(
                    {
                        "event": "tool_confirmation_required",
                        "data": {"id": tool_call.id, "name": tool_call.name, "arguments": arguments},
                    }
                )
                approved = await await_confirmation(tool_call.id)
                if not approved:
                    result = ToolResult(
                        success=False,
                        error="The user did not approve this action - do not attempt it again this turn.",
                    )
                else:
                    result = await ctx["tool_router"].call(ctx["user_id"], tool_call.name, arguments)
            else:
                result = await ctx["tool_router"].call(ctx["user_id"], tool_call.name, arguments)

        writer(
            {
                "event": "tool_result",
                "data": {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                },
            }
        )
        if tool_call.name == "generate_image" and result.success:
            try:
                generated_attachments.append(json.loads(result.output))
            except (json.JSONDecodeError, TypeError):
                pass  # malformed output shouldn't break the turn, just the image

        chat_messages.append(
            ChatMessage(
                role="tool",
                content=json.dumps({"result": result.output} if result.success else {"error": result.error}),
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )
        )

    return {"chat_messages": chat_messages, "generated_attachments": generated_attachments, "round_tool_calls": None}


def _route_after_model(state: ToolLoopState) -> str:
    if state["finish_reason"] == "tool_calls" and state["round_tool_calls"]:
        return "call_tools"
    return END


def build_tool_loop_graph():
    graph = StateGraph(ToolLoopState)
    graph.add_node("call_model", call_model_node)
    graph.add_node("call_tools", call_tools_node)
    graph.set_entry_point("call_model")
    graph.add_conditional_edges("call_model", _route_after_model, {"call_tools": "call_tools", END: END})
    graph.add_edge("call_tools", "call_model")
    return graph.compile()


# Compiled once at import time - a StateGraph is stateless config (no checkpointer here to hold
# per-run data), safe to share across every concurrent request the same way tool_router/provider
# instances already are.
TOOL_LOOP_GRAPH = build_tool_loop_graph()
