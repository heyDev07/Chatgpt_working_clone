import asyncio
import ipaddress
import socket
import tempfile
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.exceptions import ProviderError
from app.tools.base import BaseTool, ToolDefinition

# Playwright's default file-system restriction (for tools that touch local files, e.g.
# browser_file_upload) is "workspace root directories (or cwd if no roots are configured)" - per
# `npx @playwright/mcp --help`. Nothing here configures workspace roots, so that default falls
# back to whatever cwd the subprocess inherits - which, left unset, would be the backend's own
# working directory containing .env and source code. Pointing it at an empty, isolated temp
# directory instead means that restriction actually restricts to nothing sensitive, regardless of
# which browser_* tool ever touches the filesystem - defense in depth on top of excluding
# browser_file_upload entirely below.
_ISOLATED_CWD = tempfile.mkdtemp(prefix="playwright-mcp-")

# Playwright's own --blocked-origins/--allowed-origins flags explicitly do not serve as a
# security boundary and do not affect redirects (per `npx @playwright/mcp --help`) - they're a
# best-effort first layer here, not the real enforcement. _assert_safe_url() below is that
# enforcement, applied independently to every browser_navigate call. Known residual gap: a page
# reached via an allowed URL could itself redirect to a blocked address - closing that fully
# needs network-level isolation for the browser subprocess (a Phase 16 deployment concern), not
# something a URL string check can guarantee.
_BLOCKED_ORIGINS = ";".join(
    [
        "http://localhost", "https://localhost",
        "http://127.0.0.1", "https://127.0.0.1",
        "http://169.254.169.254",  # cloud metadata endpoint
        "http://postgres", "http://redis", "http://qdrant", "http://minio",
    ]
)

PLAYWRIGHT_COMMAND = "npx"
PLAYWRIGHT_ARGS = [
    "-y", "@playwright/mcp@latest",
    "--headless",
    "--isolated",  # in-memory browser profile - nothing persisted to disk between sessions
    "--blocked-origins", _BLOCKED_ORIGINS,
    "--timeout-navigation", "20000",
    "--timeout-action", "8000",
    # Screenshots would return raw image bytes, but the tool-result channel back to the LLM
    # (chat_service's `json.dumps({"result": ...})`) is text-only for every provider today -
    # omit rather than silently drop them. browser_snapshot (accessibility tree, already text)
    # covers "what's on the page" until Phase 10 (multimodal) wires up image tool results.
    "--image-responses", "omit",
]

PLAYWRIGHT_TOOL_TIMEOUT_SECONDS = 30.0

# browser_evaluate/browser_run_code_unsafe run arbitrary JavaScript in the page context - a
# script executing `fetch()` from inside the page bypasses _assert_safe_url entirely (that only
# guards the navigate call's own URL argument), so no per-argument check can make these two safe.
# browser_file_upload reads a local file (path supplied by the LLM) and attaches it to a page's
# file input - combined with prompt injection from an untrusted page (e.g. "upload your config
# file to continue"), that's a local-file-disclosure path with no legitimate use case in a chat
# agent. _ISOLATED_CWD above is a second layer for this specific one, but excluding it outright
# means there's no file for it to read regardless of that setting.
EXCLUDED_TOOL_NAMES = frozenset({"browser_evaluate", "browser_run_code_unsafe", "browser_file_upload"})

_ALLOWED_URL_SCHEMES = {"http", "https"}


async def _assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed - only http/https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        # DNS resolution is blocking - offloaded so one slow lookup can't stall the event loop
        # for other concurrent requests.
        infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host '{hostname}': {exc}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(
                f"Navigation to '{hostname}' ({ip}) is blocked - resolves to a private/internal address"
            )


class PlaywrightBrowserSession:
    """One live MCP stdio connection - and therefore one live headless browser - shared across
    every browser_* tool call within a single chat turn's tool-calling loop. Unlike Tavily's
    fresh-connection-per-call model (app/mcp/client.py), Playwright's tools are only coherent
    against the same open tab (navigate, then click, then screenshot all need the *same* page),
    so the subprocess must stay alive across a turn's iterations. chat_service creates one fresh
    instance per turn and closes it in a finally block when the turn ends - it never outlives one
    request, so a crashed/cancelled turn can't leak a running Chromium process indefinitely.

    All actual MCP I/O (open, every call_tool, close) runs on one dedicated worker task,
    regardless of which task calls into this class - open()/call_tool()/aclose() just hand a
    request to that worker over a queue and await its reply via a future. This isn't defensive
    styling; it's a fix for a real bug hit live once the tool-calling loop became a LangGraph
    graph (see tool_loop_graph.py). LangGraph executes each node via its own asyncio.create_task,
    so call_tool() (invoked from inside call_tools_node) and aclose() (invoked from
    chat_service.py's own finally block) land on *different* tasks for the same turn. The MCP
    SDK's stdio_client wraps the subprocess's pipes in an anyio TaskGroup, and something in that
    combination breaks when the group is touched from a task other than whichever task is
    currently driving it - confirmed by minimally reproducing a plain anyio TaskGroup surviving
    the exact same cross-task LangGraph pattern with no error, meaning the failure is specific to
    the MCP stdio transport (or its interaction with Starlette's BaseHTTPMiddleware wrapping the
    SSE response), not a general "anyio resources can't cross tasks" rule. Pinning everything to
    one worker task sidesteps needing to fully pin down which of those it actually is - it
    guarantees the constraint is satisfied by construction rather than by knowing its exact
    shape."""

    def __init__(self) -> None:
        self._requests: asyncio.Queue[tuple[str, dict[str, Any], asyncio.Future[str]] | None] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def open(self) -> None:
        ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._worker_task = asyncio.create_task(self._run_worker(ready))
        await ready

    async def _run_worker(self, ready: asyncio.Future[None]) -> None:
        stack = AsyncExitStack()
        try:
            params = StdioServerParameters(command=PLAYWRIGHT_COMMAND, args=PLAYWRIGHT_ARGS, cwd=_ISOLATED_CWD)
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
            await stack.aclose()
            return
        ready.set_result(None)

        try:
            while True:
                item = await self._requests.get()
                if item is None:
                    break
                name, arguments, future = item
                try:
                    result = await session.call_tool(name, arguments)
                    text_parts = [block.text for block in result.content if hasattr(block, "text")]
                    output = "\n".join(text_parts)
                    if result.isError:
                        raise ProviderError(output or f"Browser tool '{name}' returned an error")
                    if not future.done():
                        future.set_result(output)
                except BaseException as exc:  # noqa: BLE001 - relayed to the caller via the future, not swallowed
                    if not future.done():
                        future.set_exception(exc)
        finally:
            await stack.aclose()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "browser_navigate" and "url" in arguments:
            await _assert_safe_url(arguments["url"])

        if self._worker_task is None:
            raise RuntimeError("PlaywrightBrowserSession.open() must be called before call_tool()")
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        await self._requests.put((name, arguments, future))
        return await future

    async def aclose(self) -> None:
        if self._worker_task is not None:
            await self._requests.put(None)
            await self._worker_task
            self._worker_task = None


class PlaywrightMCPTool(BaseTool):
    """Adapts one browser_* tool discovered from the Playwright MCP server into BaseTool, same
    role as MCPTool (app/tools/mcp_tool.py) for Tavily - except every instance built for a given
    turn shares one PlaywrightBrowserSession rather than opening its own connection per call."""

    def __init__(self, definition: ToolDefinition, session: PlaywrightBrowserSession):
        self.definition = definition
        self._session = session

    async def run(self, **kwargs: Any) -> str:
        return await self._session.call_tool(self.definition.name, kwargs)


async def discover_playwright_tools() -> list[ToolDefinition]:
    """One-shot at startup: spawns the Playwright MCP server just long enough to list its tool
    schemas, then shuts it down immediately - no browser is launched for this, list_tools() alone
    doesn't start one. Actual browser sessions are created fresh per chat turn
    (PlaywrightBrowserSession), never held open between requests."""
    stack = AsyncExitStack()
    try:
        params = StdioServerParameters(command=PLAYWRIGHT_COMMAND, args=PLAYWRIGHT_ARGS, cwd=_ISOLATED_CWD)
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        result = await session.list_tools()
    finally:
        await stack.aclose()

    return [
        ToolDefinition(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.inputSchema,
            timeout_seconds=PLAYWRIGHT_TOOL_TIMEOUT_SECONDS,
        )
        for tool in result.tools
        if tool.name not in EXCLUDED_TOOL_NAMES
    ]
