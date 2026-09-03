"""
DriftGuard-X v2 — Jobs API
PRIVATE — All Rights Reserved.

Exposes asynchronous job status and cancellation.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.src.dependencies import get_current_tenant, require_role
from packages.contracts.src.auth import Role, User
from apps.api.src.jobs.orchestrator import orchestrator
from packages.contracts.src.auth import Tenant

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job_status(
    job_id: str, tenant: Tenant = Depends(get_current_tenant), current_user: User = Depends(require_role(Role.ADMIN))
) -> dict[str, object]:
    """Retrieve the status of a background job."""
    status_info = orchestrator.get_job_status(job_id, tenant_id=str(tenant.id))
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return status_info


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, tenant: Tenant = Depends(get_current_tenant), current_user: User = Depends(require_role(Role.ADMIN))) -> dict[str, str]:
    """Attempt to cancel a running job."""
    success = orchestrator.cancel_job(job_id, tenant_id=str(tenant.id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job could not be cancelled (may be finished or not found)",
        )
    return {"status": "cancelled"}
