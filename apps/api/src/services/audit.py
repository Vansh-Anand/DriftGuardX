"""
DriftGuard-X v2 — Audit Service
PRIVATE — All Rights Reserved.

Immutable append-only audit trail for security and governance operations.
"""
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.models import AuditEventORM

log = structlog.get_logger()


class AuditService:
    @staticmethod
    async def log_event(
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any] = None,
    ) -> AuditEventORM:
        """
        Record an immutable audit event in the database.
        Must be called for security-relevant operations: auth, RBAC, policy changes.
        """
        event = AuditEventORM(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata or {},
        )
        db.add(event)
        # Flush to ensure it's written before returning, but let caller commit transaction
        await db.flush()

        log.info(
            "audit_event",
            action=action,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return event
