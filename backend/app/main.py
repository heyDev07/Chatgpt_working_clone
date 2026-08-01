from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app import models  # noqa: F401 - ensures all models are registered before relationships resolve
from app.config.settings import get_settings
from app.core.logging_config import configure_logging
from app.core.scheduler import scheduler
from app.db.database import engine
from app.db.redis_client import get_redis
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logging import RequestLoggingMiddleware
from app.storage.s3_client import ensure_bucket_exists
from app.tools.registry import register_mcp_servers
from app.vectorstore.qdrant_client import ensure_collection
from app.vectorstore.semantic_cache import ensure_cache_collection

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    redis = get_redis()
    await redis.ping()
    await ensure_bucket_exists()
    await ensure_collection()
    await ensure_cache_collection()
    await register_mcp_servers()
    # Starts the reminders job store's own sync engine connection and resumes any pending jobs
    # already persisted from before a restart - see app/core/scheduler.py for why this needs a
    # dedicated engine rather than reusing the app's async one.
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)
    await engine.dispose()
    await redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Assistant API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    register_error_handlers(app)

    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Standard HTTP metrics (request count/latency/in-progress, labeled by method+templated-path
    # +status) - should_group_untemplated collapses /conversations/{id} variants into one series
    # instead of one per UUID, which would otherwise make this endpoint's cardinality unbounded.
    # Custom LLM/tool-call metrics (app/core/metrics.py) share the same /metrics endpoint and
    # registry - they're recorded directly at their call sites (chat_service.py, tools/router.py),
    # not through this instrumentator.
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
