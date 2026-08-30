"""
DriftGuard-X v2 — Background Worker

ARQ worker process and Redis connectivity probe.

Pipeline runs and replay episodes currently execute synchronously behind the
authenticated API.  The worker must not advertise placeholder jobs that report
success without persisting a result.  Async job handlers can be added only with
an authenticated producer, tenant-bound payload, and durable result lifecycle.

PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import os
from typing import Any, cast

import structlog
from arq.connections import RedisSettings
from arq.typing import WorkerSettingsBase

log = structlog.get_logger()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def worker_healthcheck(ctx: dict[str, Any]) -> dict[str, str]:
    """A side-effect-free job used only to verify queue execution."""
    log.info("worker.healthcheck")
    return {"status": "ok"}


# ARQ worker settings
class WorkerSettings:
    functions = [worker_healthcheck]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # 1 hour


if __name__ == "__main__":
    from arq import run_worker

    log.info("worker.starting", redis_url=REDIS_URL)
    run_worker(cast(type[WorkerSettingsBase], WorkerSettings))
