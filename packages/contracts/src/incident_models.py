"""
DriftGuard-X v2 — Incident State Models
PRIVATE — All Rights Reserved.
"""

import enum
from typing import Any

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid


class IncidentStatus(str, enum.Enum):
    OBSERVING = "OBSERVING"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    DIAGNOSING = "DIAGNOSING"
    REPLAYING = "REPLAYING"
    EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    RECOVERY_PLANNING = "RECOVERY_PLANNING"
    RECOVERY_VALIDATING = "RECOVERY_VALIDATING"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    CANARY = "CANARY"
    RECOVERED = "RECOVERED"
    RECOVERY_REJECTED = "RECOVERY_REJECTED"
    CLOSED = "CLOSED"


class IncidentState(DGXBaseModel):
    """Persists diagnostic and recovery state for an incident."""

    incident_id: str = Field(default_factory=lambda: str(_new_uuid()))
    status: IncidentStatus = IncidentStatus.OBSERVING

    root_cause_posterior: dict[str, float] = {}
    candidate_experiments: list[dict[str, Any]] = []
    completed_experiments: list[str] = []
    invalid_experiments: list[str] = []
    resource_reservations: dict[str, float] = {}

    selected_recovery_id: str | None = None
    envelope_id: str | None = None
    transport_validation_state: str | None = None

    telemetry: dict[str, Any] = {}
