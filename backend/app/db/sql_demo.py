from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.engine import make_url

from app.config.settings import get_settings


@lru_cache
def get_sql_demo_engine() -> AsyncEngine:
    """A separate engine authenticated as sql_demo_reader (see the 0eb2d0957976 migration),
    not the app's own pooled `engine` from db/database.py - LLM-generated SQL must run under a
    role that is physically incapable of touching `public.*` or writing anything, not just a
    role that happens to share a connection pool with code that promises to behave."""
    settings = get_settings()
    url = make_url(settings.database_url).set(
        username="sql_demo_reader", password=settings.sql_demo_db_password
    )
    return create_async_engine(url, pool_pre_ping=True, pool_size=2)
