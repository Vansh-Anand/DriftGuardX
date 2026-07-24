"""
DriftGuard-X v2 — Auth Data Contracts
PRIVATE — All Rights Reserved.

Defines schemas for Identity, Tenant, and RBAC models.
"""
import enum
from typing import List
from uuid import UUID

from pydantic import Field
from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow
from datetime import datetime

class Role(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    SYSTEM = "system"


class Tenant(DGXBaseModel):
    id: UUID = Field(default_factory=_new_uuid)
    name: str
    created_at: datetime = Field(default_factory=_utcnow)


class User(DGXBaseModel):
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    email: str
    roles: List[Role]
    created_at: datetime = Field(default_factory=_utcnow)


class APIKey(DGXBaseModel):
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    key_hash: str
    scopes: List[str]
    created_at: datetime = Field(default_factory=_utcnow)


class AuditEvent(DGXBaseModel):
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: str
    metadata_json: str
    created_at: datetime = Field(default_factory=_utcnow)
