import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401 - ensures all models are registered before relationships resolve
from app.config.settings import get_settings
from app.db.database import engine
from app.db.redis_client import get_redis
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    redis = get_redis()
    await redis.ping()

    yield

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

    return app


app = create_app()
