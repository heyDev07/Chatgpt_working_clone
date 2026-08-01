"""Retry wrapper for outbound calls to third-party OAuth providers (Google, LinkedIn) -
diagnosed live (not guessed) on this deployment: IPv4 connections to Google's servers are being
reset by something in the local network path, while IPv6 to the exact same host succeeds
reliably, and DNS returns both. Whichever family a given connection attempt happens to pick
determines success/failure, which is why the same code intermittently fails - confirmed by
running the identical httpx call in a tight loop and separately by `curl -4` vs `curl -6` against
the same URL. A transient connection failure that would very likely succeed on an immediate retry
(the next attempt has a real chance of landing on IPv6 instead) is exactly what a short retry
loop is for - this doesn't fix the underlying network path, but it does stop that path problem
from being user-visible as a failed login/connect.
"""

import asyncio

import httpx

RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectTimeout)


async def request_with_retry(
    client: httpx.AsyncClient, method: str, url: str, *, max_attempts: int = 3, **kwargs
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await client.request(method, url, **kwargs)
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc
