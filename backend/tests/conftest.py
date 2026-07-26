"""Integration test infrastructure - real Postgres, real Redis, real FastAPI app, no mocks.
Matches this project's whole verification philosophy (run it against real infra, don't assume),
just automated instead of a curl session.

Uses a dedicated database (ai_assistant_test, on the same local Postgres docker-compose already
runs) and a dedicated Redis logical DB index (1, vs. dev's 0) - never touches real dev data or
dev rate-limit counters. Requires the project's usual `docker compose up -d` infra to be running;
these are integration tests, not unit tests, and don't try to fake that requirement away.
DATABASE_URL/REDIS_URL are set here, before app.main is ever imported, so get_settings()'s
@lru_cache picks up the test values on its one and only call - the app's real, unmodified
get_db_session/get_redis dependencies then naturally point at the test infra with no dependency
overrides needed at all.

Tests hit a real running uvicorn server over real HTTP, in a background thread with its own event
loop - not httpx's in-process ASGITransport (RequestLoggingMiddleware, a BaseHTTPMiddleware like
every ASGI middleware in this app, hits a documented Starlette/anyio incompatibility with
ASGITransport specifically - confirmed live by testing with that middleware stripped out, which
then worked) and not a same-loop asyncio.create_task() server either (confirmed live too: that
produced a real, successful 201 response server-side while the client that "sent" it was still
stuck waiting, since a single loop can't fairly interleave a blocking-ish request handler with the
client coroutine awaiting its response).

Every fixture except the test-facing `client` itself is a plain sync fixture that does its async
work via a self-contained asyncio.run() call, rather than an async pytest-asyncio fixture. Not
required for correctness (see pytest.ini: asyncio_default_test_loop_scope=session is the actual
fix for the loop-scope mismatch this used to hit - fixtures and tests were on session/function
loops respectively, so a fixture set up on one loop got torn down on a different, already-closed
one, surfacing as "RuntimeError: Event loop is closed" deep in httpx/anyio's transport cleanup).
Kept anyway since these are one-shot setup/teardown steps with nothing to yield across an await
boundary - a plain sync fixture is simpler than an async one here regardless of loop scoping.
"""

import asyncio
import os
import threading
import time

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://ai_assistant:ai_assistant@localhost:5433/ai_assistant_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-real-use")

import pytest
import pytest_asyncio
import uvicorn
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import app
from app.models import Base

TEST_SERVER_PORT = 8765


@pytest.fixture(scope="session")
def test_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=TEST_SERVER_PORT, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield
    server.should_exit = True
    thread.join(timeout=5)


async def _create_all() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def _drop_all() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _truncate_all() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()


async def _flush_redis() -> None:
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.flushdb()
    await client.aclose()


@pytest.fixture(scope="session")
def _schema():
    asyncio.run(_create_all())
    yield
    asyncio.run(_drop_all())


@pytest.fixture
def clean_db(_schema):
    # Truncated before each test, not rolled back after - services (AuthService.register, etc.)
    # commit directly rather than just flushing, so there's real committed data from the
    # *previous* test to clear, not an in-memory transaction a rollback could undo.
    asyncio.run(_truncate_all())
    yield


@pytest.fixture
def clean_redis():
    asyncio.run(_flush_redis())
    yield
    asyncio.run(_flush_redis())


@pytest_asyncio.fixture
async def client(test_server, clean_db, clean_redis):
    async with AsyncClient(base_url=f"http://127.0.0.1:{TEST_SERVER_PORT}") as ac:
        yield ac
