"""
DriftGuard-X v2 — Jobs API
PRIVATE — All Rights Reserved.

Exposes asynchronous job status and cancellation.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from apps.api.src.jobs.orchestrator import orchestrator
from apps.api.src.dependencies import get_current_user

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

@router.get("/{job_id}")
async def get_job_status(job_id: str, user = Depends(get_current_user)):
    """Retrieve the status of a background job."""
    status_info = orchestrator.get_job_status(job_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return status_info

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, user = Depends(get_current_user)):
    """Attempt to cancel a running job."""
    success = orchestrator.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job could not be cancelled (may be finished or not found)",
        )
    return {"status": "cancelled"}
