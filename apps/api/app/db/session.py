from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine_kwargs: dict[str, Any] = {
    "echo": settings.ENVIRONMENT == "development",
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if settings.DB_POOLER_MODE:
    # Serverless PgBouncer / Neon pooler mode:
    # Disable prepared statement caching (incompatible with PgBouncer transaction mode)
    # but maintain a small client-side connection pool to eliminate TCP handshake latency
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine: AsyncEngine = create_async_engine(settings.clean_database_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an active async SQLAlchemy database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Dispose of the persistent database connection pool on shutdown."""
    await engine.dispose()
