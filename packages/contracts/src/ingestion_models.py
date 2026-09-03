"""
DriftGuard-X v2 — Ingestion Models
PRIVATE — All Rights Reserved.
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _utcnow


class ExecutionMode(str, enum.Enum):
    SYNTHETIC_SIMULATION = "synthetic_simulation"
    CONTROLLED_REPLAY = "controlled_replay"
    PRODUCTION_CANARY = "production_canary"
    PRODUCTION = "production"


class ExternalRunRegistration(DGXBaseModel):
    tenant_id: UUID
    pipeline_id: UUID
    external_run_id: str
    execution_mode: ExecutionMode = ExecutionMode.PRODUCTION
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
