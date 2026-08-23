import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from packages.contracts.src.recovery_models import SignedCapability


class AccessContext(BaseModel):
    requester_id: str
    tenant_id: str
    authenticated_roles: list[str] = Field(default_factory=list)
    capabilities: list[SignedCapability] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    integrity_hash: str | None = None

    def is_valid(self) -> bool:
        return datetime.now(UTC) <= self.expires_at

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requester: str
    tenant: str
    partition: str
    action: str
    capability_id: str | None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy_version: str
    result: str
    event_hash: str | None = None
