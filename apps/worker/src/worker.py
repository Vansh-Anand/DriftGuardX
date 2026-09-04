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


async def run_recovery_diagnosis(ctx: dict[str, Any], job_id: str, tenant_id: str, run_id: str, failure_symptom: str, invocations_data: list[dict]) -> dict[str, Any]:
    """Execute the recovery loop in the background."""
    from apps.api.src.database import async_session_maker
    from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
    from apps.api.src.models import JobORM
    from packages.contracts.src.agent_models import AgentInvocation
    import uuid
    from datetime import datetime, UTC
    
    log.info("Starting run_recovery_diagnosis", job_id=job_id, run_id=run_id)
    
    invocations = [AgentInvocation(**inv) for inv in invocations_data]
    
    async with async_session_maker() as db:
        # Update job to RUNNING
        from sqlalchemy import select
        job_result = await db.execute(select(JobORM).where(JobORM.id == uuid.UUID(job_id)))
        job_orm = job_result.scalar_one_or_none()
        if job_orm:
            job_orm.status = "RUNNING"
            job_orm.started_at = datetime.now(UTC)
            await db.commit()
            
        try:
            pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)
            approval_req = await pipeline.execute_recovery_loop(run_id, invocations, failure_symptom, db)
            await db.commit()
            
            # Update job to SUCCEEDED
            if job_orm:
                job_orm.status = "SUCCEEDED"
                job_orm.completed_at = datetime.now(UTC)
                job_orm.result = {"approval_request_id": str(approval_req.id)} if approval_req else {"status": "no_candidates"}
                await db.commit()
                
            return {"status": "success", "approval_request_id": str(approval_req.id) if approval_req else None}
            
        except Exception as e:
            await db.rollback()
            log.exception("Recovery diagnosis failed", job_id=job_id, exc_info=e)
            if job_orm:
                job_orm.status = "FAILED"
                job_orm.completed_at = datetime.now(UTC)
                job_orm.error = str(e)
                await db.commit()
            raise e



# ARQ worker settings
class WorkerSettings:
    functions = [worker_healthcheck, run_recovery_diagnosis]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # 1 hour


if __name__ == "__main__":
    from arq import run_worker

    log.info("worker.starting", redis_url=REDIS_URL)
    run_worker(cast(type[WorkerSettingsBase], WorkerSettings))
