from typing import List, Optional, Set
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class AccessContext(BaseModel):
    requester_id: str
    tenant_id: str
    authenticated_roles: List[str] = Field(default_factory=list)
    capability_ids: List[str] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    integrity_hash: Optional[str] = None
    
    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) <= self.expires_at

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requester: str
    tenant: str
    partition: str
    action: str
    capability_id: Optional[str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version: str
    result: str
    event_hash: Optional[str] = None
