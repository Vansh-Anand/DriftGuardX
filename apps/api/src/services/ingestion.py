"""
DriftGuard-X v2 — Span Ingestion Service

Handles idempotent insertion of spans, late-arriving spans, and
dead-letter logging for malformed telemetry.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from apps.api.src.models import RequestRunORM, SpanRecordORM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
        errors: list[str] = []

        # Dedup incoming payload by span_id
        unique_spans = {s.span_id: s for s in spans}.values()

        for item in unique_spans:
            try:
                async with self.db.begin_nested():
                    scoped_run = await self.db.scalar(
                        select(RequestRunORM.id).where(
                            RequestRunORM.id == item.run_id,
                            RequestRunORM.tenant_id == item.tenant_id,
                            RequestRunORM.pipeline_id == item.pipeline_id,
                        )
                    )
                    if scoped_run is None:
                        raise ValueError("run scope mismatch")

                    existing_span = await self.db.scalar(
                        select(SpanRecordORM.id).where(
                            SpanRecordORM.tenant_id == item.tenant_id,
                            SpanRecordORM.span_id == item.span_id,
                        )
                    )
                    if existing_span is not None:
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
                        status_code=item.status_code,
                        attributes_json=item.attributes,
                        component_type=item.attributes.get("dgx.component.type"),
                        component_version_tag=item.attributes.get("dgx.component.version_tag"),
                        input_hash=item.attributes.get("dgx.payload.input_hash"),
                        output_hash=item.attributes.get("dgx.payload.output_hash"),
                    )

                    cv_id = item.attributes.get("dgx.component.version_id")
                    if cv_id:
                        span_orm.component_version_id = UUID(str(cv_id))

                    self.db.add(span_orm)
                    await self.db.flush()
                ingested += 1
            except (SQLAlchemyError, ValueError, TypeError):
                skipped += 1
                logger.exception("span_ingestion_rejected", extra={"span_id": item.span_id})
                errors.append(f"span {item.span_id}: rejected")

        return ingested, skipped, errors


async def get_ingestion_service(db: AsyncSession) -> IngestionService:
    return IngestionService(db)
