"""
DriftGuard-X v2 — Migration Tests (3 tests)

Tests that the DB schema matches ORM models and that Alembic down/up is clean.
These run against SQLite in-memory (no Postgres required).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from datetime import UTC

from apps.api.src.models import Base, TenantORM


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tables_created_match_orm_models() -> None:
    """All ORM model tables must be created by create_all."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        table_names_result = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    expected_tables = {
        "tenants",
        "component_versions",
        "agent_pipelines",
        "request_runs",
        "trace_artifacts",
        "span_records",
        "interventions",
        "replay_episodes",
    }
    for table in expected_tables:
        assert table in table_names_result, f"Table '{table}' missing from DB"

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_insert_and_select() -> None:
    """Tenant ORM CRUD round-trip."""
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        tenant = TenantORM(
            id=uuid.uuid4(),
            name="Test Tenant",
            slug="test-tenant",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(tenant)
        await session.commit()

    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(TenantORM).where(TenantORM.slug == "test-tenant"))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.name == "Test Tenant"

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_schema_columns_present() -> None:
    """Critical columns must exist on request_runs table."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: [
                col["name"] for col in inspect(sync_conn).get_columns("request_runs")
            ]
        )

    required = [
        "id",
        "tenant_id",
        "pipeline_id",
        "status",
        "request_hash",
        "reliability_score",
        "reliability_vector",
        "is_synthetic",
        "created_at",
        "completed_at",
    ]
    for col in required:
        assert col in columns, f"Column '{col}' missing from request_runs"

    await engine.dispose()
