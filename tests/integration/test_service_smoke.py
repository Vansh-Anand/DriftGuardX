"""Live PostgreSQL and Redis connectivity smoke tests used by CI."""

import os

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_and_redis_services_are_live() -> None:
    database_url = os.getenv("DGX_SERVICE_DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")
    if not database_url.startswith("postgresql+") or not redis_url:
        pytest.skip("Live PostgreSQL and Redis endpoints are not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()

    redis = Redis.from_url(redis_url)
    try:
        assert await redis.ping() is True
    finally:
        await redis.aclose()
