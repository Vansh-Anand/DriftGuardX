"""
DriftGuard-X v2 — Async Job Orchestrator
PRIVATE — All Rights Reserved.

In-memory async job queue for graph builds, evaluations, and replays.
Provides state exposure and cancellation semantics.
"""
import asyncio
import enum
import time
import uuid
from typing import Dict, Any, Callable, Coroutine
from dataclasses import dataclass, field

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "generic"
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: str = None
    created_at: float = field(default_factory=time.time)
    started_at: float = None
    completed_at: float = None
    _task: asyncio.Task = None

class JobOrchestrator:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
    
    def submit_job(self, task_type: str, coro_func: Callable[..., Coroutine], *args, **kwargs) -> str:
        job = Job(task_type=task_type)
        self.jobs[job.id] = job
        
        async def wrapper():
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            try:
                # We await the user provided coroutine
                result = await coro_func(*args, **kwargs)
                if job.status != JobStatus.CANCELLED:
                    job.status = JobStatus.COMPLETED
                    job.result = result
            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
            finally:
                job.completed_at = time.time()
        
        # Schedule the background task
        task = asyncio.create_task(wrapper())
        job._task = task
        return job.id
    
    def get_job_status(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "task_type": job.task_type,
            "status": job.status,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }
    
    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
            
        if job._task:
            job._task.cancel()
            job.status = JobStatus.CANCELLED
            return True
        return False

# Global orchestrator for the prototype
orchestrator = JobOrchestrator()
