"""Human-in-the-loop gate for tools marked permission_level="restricted" (see app/tools/base.py) -
send_gmail/create_calendar_event and anything else with a real-world, hard-to-undo side effect.

The tool-calling loop (tool_loop_graph.py) runs inside chat_service.py's independent background
asyncio.Task (_stream_resilient), which outlives the original HTTP request - so approving a
pending call has to come from a *separate*, later request (the user clicking Approve in the UI),
not a return value the loop itself can wait on synchronously. An in-memory dict of asyncio.Future
keyed by the tool call's id is what lets that second request hand a result back into the first
request's still-running coroutine. Same "module-level registry keyed by an id, single-process
dev server" pattern chat_service.py already uses for stop-generation
(_background_generation_tasks), not a new architectural idea.

Not persisted to the database or backed by Redis - if the process restarts mid-confirmation the
pending call is simply lost (the loop's asyncio.wait_for below times out and treats it as
declined). Acceptable for a single-instance deployment; a horizontally-scaled one would need this
in Redis instead, same as the reminder scheduler's job store would.
"""

import asyncio

CONFIRMATION_TIMEOUT_SECONDS = 300  # 5 minutes - long enough for a user to actually notice and
# act on the prompt, short enough that a turn doesn't hang indefinitely if they never do.

_pending: dict[str, asyncio.Future[bool]] = {}


async def await_confirmation(call_id: str) -> bool:
    """Blocks the calling coroutine until resolve_confirmation(call_id, ...) is called from a
    separate request, or the timeout elapses (treated as a decline, not an error - a user who
    walked away shouldn't have the assistant guess and act anyway)."""
    future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
    _pending[call_id] = future
    try:
        return await asyncio.wait_for(future, timeout=CONFIRMATION_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return False
    finally:
        _pending.pop(call_id, None)


def resolve_confirmation(call_id: str, approved: bool) -> bool:
    """Called from the API route the frontend's Approve/Reject buttons hit. Returns False if
    there's nothing to resolve (already timed out, already resolved, or the id is bogus) so the
    route can tell the difference from a real success rather than silently no-op."""
    future = _pending.get(call_id)
    if future is None or future.done():
        return False
    future.set_result(approved)
    return True
