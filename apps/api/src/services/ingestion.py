"""
DriftGuard-X v2 — Span Ingestion Service

Handles idempotent insertion of spans, late-arriving spans, and 
dead-letter logging for malformed telemetry.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.src.models import SpanRecordORM, TraceArtifactORM
from apps.api.src.schemas import SpanIngestItem

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_spans(self, spans: list[SpanIngestItem]) -> tuple[int, int, list[str]]:
        """
        Process incoming spans idempotently.
        Returns (ingested_count, skipped_count, errors_list).
        """
        ingested = 0
        skipped = 0
        errors = []

        # Dedup incoming payload by span_id
        unique_spans = {s.span_id: s for s in spans}.values()

        for item in unique_spans:
            try:
                # Idempotency check: see if span already exists
                stmt = select(SpanRecordORM).where(SpanRecordORM.span_id == item.span_id)
                result = await self.db.execute(stmt)
                existing_span = result.scalar_one_or_none()

                if existing_span:
                    # Idempotent skip or update (we choose skip to prevent tampering)
                    skipped += 1
                    continue
                
                span_orm = SpanRecordORM(
                    trace_id=item.trace_id,
                    span_id=item.span_id,
                    parent_span_id=item.parent_span_id,
                    run_id=item.run_id,
                    tenant_id=item.tenant_id,
                    pipeline_id=item.pipeline_id,
                    name=item.name,
                    kind=item.kind,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    status_code="UNSET",
                    attributes_json=item.attributes,
                    
                    # Store these fields if they exist in attributes
                    component_type=item.attributes.get("dgx.component.type"),
                    component_version_tag=item.attributes.get("dgx.component.version_tag"),
                    input_hash=item.attributes.get("dgx.payload.input_hash"),
                    output_hash=item.attributes.get("dgx.payload.output_hash"),
                )
                
                # Check for component_version_id
                cv_id = item.attributes.get("dgx.component.version_id")
                if cv_id:
                    span_orm.component_version_id = UUID(cv_id)
                    
                self.db.add(span_orm)
                ingested += 1

                # We could run completeness checks asynchronously here, 
                # but typically that's done via a cron or end-of-run trigger.

            except Exception as e:
                skipped += 1
                error_msg = f"span {item.span_id}: {type(e).__name__} - {str(e)}"
                logger.error(f"Failed to ingest span: {error_msg}")
                # Future: Send to Dead-Letter Queue
                errors.append(error_msg)

        await self.db.flush()
        return ingested, skipped, errors


async def get_ingestion_service(db: AsyncSession) -> IngestionService:
    return IngestionService(db)
