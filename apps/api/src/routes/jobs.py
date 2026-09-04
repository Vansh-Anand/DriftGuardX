"""
DriftGuard-X v2 — Jobs API
PRIVATE — All Rights Reserved.

Exposes persistent asynchronous job status and cancellation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant, require_role
from apps.api.src.jobs.orchestrator import orchestrator
from packages.contracts.src.auth import Role, Tenant, User

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, object]:
    """Retrieve the status of a background job from PostgreSQL."""
    status_info = await orchestrator.get_job_status(job_id, tenant_id=str(tenant.id), db=db)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    return status_info


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, str]:
    """Attempt to cancel a running job in PostgreSQL and terminate its task."""
    success = await orchestrator.cancel_job(job_id, tenant_id=str(tenant.id), db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job could not be cancelled (may be finished or not found)",
        )
    return {"status": "cancelled"}
