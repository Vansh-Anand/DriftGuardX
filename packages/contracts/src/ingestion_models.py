"""
DriftGuard-X v2 — Ingestion Models
PRIVATE — All Rights Reserved.
"""
from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class ExternalRunRegistration(DGXBaseModel):
    tenant_id: UUID
    pipeline_id: UUID
    external_run_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
