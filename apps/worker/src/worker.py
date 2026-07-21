"""
DriftGuard-X v2 — Background Worker

ARQ-based async worker for background pipeline execution and replay jobs.
In Prompt 01: runs inline without a live Redis instance when REDIS_URL is not set.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import structlog

log = structlog.get_logger()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def execute_run_job(ctx: dict[str, Any], run_id: str, query: str, seed: int = 42) -> dict[str, Any]:
    """
    Background job: Execute a pipeline run.
    Persists result to DB via the API layer.
    """
    log.info("worker.execute_run", run_id=run_id, query_length=len(query))
    # In Prompt 01 — execution is done synchronously in the API handler.
    # This worker stub is a placeholder for async offloading in future prompts.
    return {"status": "completed", "run_id": run_id}


async def execute_replay_job(ctx: dict[str, Any], run_id: str, seed: int = 42) -> dict[str, Any]:
    """
    Background job: Execute a replay episode.
    """
    log.info("worker.execute_replay", run_id=run_id)
    return {"status": "completed", "run_id": run_id}


# ARQ worker settings
class WorkerSettings:
    functions = [execute_run_job, execute_replay_job]
    redis_settings_from_dsn = REDIS_URL
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # 1 hour


if __name__ == "__main__":
    import asyncio
    log.info("worker.starting", redis_url=REDIS_URL)
    # arq.run_worker(WorkerSettings) — requires live Redis
    # For Prompt 01 dev mode, print a warning and exit
    log.warning(
        "worker.dev_mode",
        message="Worker requires Redis. Set REDIS_URL and use 'arq apps.worker.src.worker.WorkerSettings'",
    )
