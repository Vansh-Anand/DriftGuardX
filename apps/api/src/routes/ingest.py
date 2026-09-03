"""
DriftGuard-X v2 — Span Ingestion Route

POST /v1/ingest/spans — OpenTelemetry-compatible span ingestion
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from apps.api.src.database import get_db
from apps.api.src.dependencies import get_current_tenant
from apps.api.src.schemas import SpanIngestRequest, SpanIngestResponse
from apps.api.src.services.ingestion import IngestionService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post("/ingest/spans", response_model=SpanIngestResponse)
async def ingest_spans(
    request: SpanIngestRequest,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> SpanIngestResponse:
    """Ingest raw OpenTelemetry-compatible spans."""
    if any(span.tenant_id != tenant.id for span in request.spans):
        raise HTTPException(
            status_code=403, detail="Span tenant does not match authenticated tenant"
        )
    ingestion_service = IngestionService(db)
    ingested, skipped, errors = await ingestion_service.ingest_spans(request.spans)
    return SpanIngestResponse(ingested=ingested, skipped=skipped, errors=errors)
