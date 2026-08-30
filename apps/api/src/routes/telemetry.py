"""
DriftGuard-X v2 — Telemetry Quality and Search API
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.models import SpanRecordORM, TraceArtifactORM
from packages.contracts.src.auth import Tenant

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


@router.get("/quality")
async def get_telemetry_quality(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """Retrieve telemetry quality statistics for the authenticated tenant."""
    # 1. Total Spans
    total_spans_stmt = select(func.count(SpanRecordORM.id)).where(
        SpanRecordORM.tenant_id == tenant.id
    )
    total_spans = await db.scalar(total_spans_stmt) or 0

    # 2. Total Traces
    total_traces_stmt = select(func.count(TraceArtifactORM.id)).where(
        TraceArtifactORM.tenant_id == tenant.id
    )
    total_traces = await db.scalar(total_traces_stmt) or 0

    # 3. Missing Component Tags (Missing component_version_tag)
    missing_tags_stmt = select(func.count(SpanRecordORM.id)).where(
        SpanRecordORM.tenant_id == tenant.id, SpanRecordORM.component_version_tag.is_(None)
    )
    missing_tags = await db.scalar(missing_tags_stmt) or 0

    # 4. Total errors recorded
    errors_stmt = select(func.count(SpanRecordORM.id)).where(
        SpanRecordORM.tenant_id == tenant.id, SpanRecordORM.status_code == "ERROR"
    )
    errors = await db.scalar(errors_stmt) or 0

    latest_span_time = await db.scalar(
        select(func.max(func.coalesce(SpanRecordORM.end_time, SpanRecordORM.start_time))).where(
            SpanRecordORM.tenant_id == tenant.id
        )
    )
    if latest_span_time is not None:
        if latest_span_time.tzinfo is None:
            latest_span_time = latest_span_time.replace(tzinfo=UTC)
        ingestion_lag_ms: float | None = max(
            0.0, (datetime.now(UTC) - latest_span_time).total_seconds() * 1000
        )
    else:
        ingestion_lag_ms = None

    return {
        "tenant_id": str(tenant.id),
        "metrics": {
            "total_spans": total_spans,
            "total_traces": total_traces,
            "spans_missing_tags": missing_tags,
            "total_errors": errors,
            "duplicate_rate": None,
            "ingestion_lag_ms": ingestion_lag_ms,
        },
    }


@router.get("/search")
async def search_traces(
    limit: int = Query(default=50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> dict[str, Any]:
    """Basic Tenant-Scoped Trace Search"""
    stmt = (
        select(TraceArtifactORM)
        .where(TraceArtifactORM.tenant_id == tenant.id)
        .order_by(TraceArtifactORM.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    traces = result.scalars().all()

    return {
        "results": [
            {
                "trace_id": str(t.run_id),  # We use run_id as primary reference
                "created_at": t.created_at,
                "span_count": t.total_span_count,
                # Completeness is not persisted on TraceArtifactORM yet. Do not
                # invent a score at read time; clients can distinguish unknown
                # from a measured zero.
                "completeness_score": None,
            }
            for t in traces
        ]
    }
