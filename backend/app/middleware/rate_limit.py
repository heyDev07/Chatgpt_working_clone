from redis.asyncio import Redis

from app.core.exceptions import RateLimitError


class RateLimiter:
    """Fixed-window rate limiter backed by Redis. Used as a FastAPI dependency."""

    def __init__(self, key_prefix: str, max_requests: int, window_seconds: int):
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def check(self, redis: Redis, identifier: str) -> None:
        key = f"rate_limit:{self.key_prefix}:{identifier}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, self.window_seconds)
        if current > self.max_requests:
            raise RateLimitError("Too many requests, please slow down")


login_rate_limiter = RateLimiter(key_prefix="login", max_requests=10, window_seconds=60)
message_rate_limiter = RateLimiter(key_prefix="message", max_requests=20, window_seconds=60)
# Unauthenticated - registration has no user identity yet to key on, so the limiter is applied
# per-IP instead (see auth.py). A generous window: this is anti-automation, not anti-abuse of an
# already-known account.
register_rate_limiter = RateLimiter(key_prefix="register", max_requests=5, window_seconds=300)
# Every tool call is a real resource cost - an external API request (Tavily), a spawned headless
# Chromium process (Playwright), or a DB query (sql_query) - none of which the calculator-only
# assumption this endpoint originally shipped under accounted for.
tool_call_rate_limiter = RateLimiter(key_prefix="tool_call", max_requests=30, window_seconds=60)
# Document parsing/embedding and image storage both cost real compute/storage - same reasoning
# as tool calls above.
upload_rate_limiter = RateLimiter(key_prefix="upload", max_requests=20, window_seconds=60)
# A confirmation gate alone doesn't cap how many real applications get submitted - it only
# guarantees each one was approved, not that approving many in a row was a good idea. This is an
# independent backstop against rapid-fire submission (accidental or otherwise), not a substitute
# for the confirmation step.
job_application_rate_limiter = RateLimiter(key_prefix="job_application", max_requests=10, window_seconds=86400)
# Deep Research is a multi-call, multi-search pipeline per turn - far more expensive than a
# normal message even before counting web-search cost, so it gets its own cap independent of
# message_rate_limiter's general per-minute one.
research_rate_limiter = RateLimiter(key_prefix="research", max_requests=10, window_seconds=3600)
