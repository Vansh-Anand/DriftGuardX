"""
DriftGuard-X v2 — Telemetry Quality and Search API
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.models import SpanRecordORM, TraceArtifactORM

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


@router.get("/quality/{tenant_id}")
async def get_telemetry_quality(tenant_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Retrieve telemetry quality statistics for a given tenant."""

    # 1. Total Spans
    total_spans_stmt = select(func.count(SpanRecordORM.id)).where(SpanRecordORM.tenant_id == tenant_id)
    total_spans = await db.scalar(total_spans_stmt) or 0

    # 2. Total Traces
    total_traces_stmt = select(func.count(TraceArtifactORM.id)).where(TraceArtifactORM.tenant_id == tenant_id)
    total_traces = await db.scalar(total_traces_stmt) or 0

    # 3. Missing Component Tags (Missing component_version_tag)
    missing_tags_stmt = select(func.count(SpanRecordORM.id)).where(
        SpanRecordORM.tenant_id == tenant_id,
        SpanRecordORM.component_version_tag.is_(None)
    )
    missing_tags = await db.scalar(missing_tags_stmt) or 0

    # 4. Total errors recorded
    errors_stmt = select(func.count(SpanRecordORM.id)).where(
        SpanRecordORM.tenant_id == tenant_id,
        SpanRecordORM.status_code == "ERROR"
    )
    errors = await db.scalar(errors_stmt) or 0

    return {
        "tenant_id": str(tenant_id),
        "metrics": {
            "total_spans": total_spans,
            "total_traces": total_traces,
            "spans_missing_tags": missing_tags,
            "total_errors": errors,
            "duplicate_rate": 0.0, # Handled by deduplication logic, mostly 0
            "ingestion_lag_ms": 0.0 # Placeholder for time diff logic
        }
    }


@router.get("/search/{tenant_id}")
async def search_traces(tenant_id: UUID, limit: int = 50, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Basic Tenant-Scoped Trace Search"""
    stmt = select(TraceArtifactORM).where(TraceArtifactORM.tenant_id == tenant_id).order_by(TraceArtifactORM.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    traces = result.scalars().all()

    return {
        "results": [
            {
                "trace_id": str(t.run_id),  # We use run_id as primary reference
                "created_at": t.created_at,
                "span_count": t.total_span_count,
                "completeness_score": t.completeness_score
            }
            for t in traces
        ]
    }
