import asyncio
import ipaddress
import socket
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.exceptions import ProviderError
from app.tools.base import BaseTool, ToolDefinition

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
# Excluded from discovery rather than offered half-protected.
EXCLUDED_TOOL_NAMES = frozenset({"browser_evaluate", "browser_run_code_unsafe"})

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
    request, so a crashed/cancelled turn can't leak a running Chromium process indefinitely."""

    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def _ensure_started(self) -> ClientSession:
        if self._session is None:
            stack = AsyncExitStack()
            params = StdioServerParameters(command=PLAYWRIGHT_COMMAND, args=PLAYWRIGHT_ARGS)
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            self._stack = stack
            self._session = session
        return self._session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "browser_navigate" and "url" in arguments:
            await _assert_safe_url(arguments["url"])

        session = await self._ensure_started()
        result = await session.call_tool(name, arguments)
        text_parts = [block.text for block in result.content if hasattr(block, "text")]
        output = "\n".join(text_parts)
        if result.isError:
            raise ProviderError(output or f"Browser tool '{name}' returned an error")
        return output

    async def aclose(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None


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
        params = StdioServerParameters(command=PLAYWRIGHT_COMMAND, args=PLAYWRIGHT_ARGS)
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
