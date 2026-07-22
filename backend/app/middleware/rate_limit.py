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
