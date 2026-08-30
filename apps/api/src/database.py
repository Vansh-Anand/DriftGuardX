"""
DriftGuard-X v2 — Database Configuration

Async SQLAlchemy engine with PostgreSQL. Falls back to SQLite for testing.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

import apps.api.src.models_ingestion
import apps.api.src.models_manifest  # noqa: F401
from apps.api.src.config import settings
from apps.api.src.models import Base


@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


# Default: SQLite for local dev without Docker; override via env
_DB_URL = settings.database_url.get_secret_value()

# Use NullPool for SQLite (no connection pooling needed)
_USE_NULLPOOL = _DB_URL.startswith("sqlite")

engine = create_async_engine(
    _DB_URL,
    echo=os.environ.get("DB_ECHO", "false").lower() == "true",
    poolclass=NullPool if _USE_NULLPOOL else None,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables (for testing / SQLite dev). Use Alembic for Postgres."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Drop all tables (for testing only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
