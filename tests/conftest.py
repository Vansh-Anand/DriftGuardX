"""
DriftGuard-X v2 — Shared test fixtures and configuration.
"""

from __future__ import annotations

import os
import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Preserve a CI-provided live database for the explicit service smoke test,
# while keeping application fixtures hermetic and fast.
os.environ.setdefault("DGX_SERVICE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
# Force SQLite for application-level tests.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault(
    "DGX_CAPABILITY_SECRET",
    "driftguardx-test-capability-secret-32-bytes-minimum",
)
os.environ.setdefault(
    "DGX_TRANSPORT_KEY",
    "driftguardx-test-transport-secret-32-bytes-minimum",
)

from typing import TYPE_CHECKING

from apps.api.src.database import Base, get_db
from apps.api.src.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ─── Async Engine ─────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create tables once for the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_test_db: None) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test DB session with rollback after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(setup_test_db: None) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with DB override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except (ValueError, RuntimeError, KeyError, TypeError, OSError):
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.headers["Authorization"] = "Bearer mock-admin-token"
        yield ac

    app.dependency_overrides.clear()


# ─── Test Data Builders ───────────────────────────────────────────────────────


def make_tenant_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-FFFF-000000000001")


def make_pipeline_id(experimental: bool = False) -> uuid.UUID:
    if experimental:
        return uuid.UUID("00000000-0000-0000-AAAA-000000000002")
    return uuid.UUID("00000000-0000-0000-AAAA-000000000001")
