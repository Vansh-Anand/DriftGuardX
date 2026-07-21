"""
DriftGuard-X v2 — Span Ingestion Route

POST /v1/ingest/spans — OpenTelemetry-compatible span ingestion
"""
from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.database import get_db
from apps.api.src.models import SpanRecordORM
from apps.api.src.schemas import SpanIngestRequest, SpanIngestResponse
from apps.api.src.services.ingestion import IngestionService

router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post("/ingest/spans", response_model=SpanIngestResponse)
async def ingest_spans(
    request: SpanIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> SpanIngestResponse:
    """Ingest raw OpenTelemetry-compatible spans."""
    ingestion_service = IngestionService(db)
    ingested, skipped, errors = await ingestion_service.ingest_spans(request.spans)
    return SpanIngestResponse(ingested=ingested, skipped=skipped, errors=errors)
