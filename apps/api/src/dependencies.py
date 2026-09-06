"""
DriftGuard-X v2 — FastAPI Dependencies
PRIVATE — All Rights Reserved.

Provides dependency injection for Tenant Isolation, RBAC, and Pagination.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.auth import MOCK_TENANT, MOCK_USER, oauth2_scheme, verify_token
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.models import TenantMembershipORM, TenantORM, UserORM
from packages.contracts.src.auth import Role, Tenant, User


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    x_driftguard_role: str | None = Header(None, alias="X-DriftGuard-Role"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verifies the JWT and returns the User object."""
    if settings.auth_mode == "mock" and token == "mock-admin-token":
        roles = [Role(x_driftguard_role)] if x_driftguard_role else MOCK_USER.roles
        return User(
            id=MOCK_USER.id,
            tenant_id=MOCK_USER.tenant_id,
            email=MOCK_USER.email,
            roles=[Role(r) for r in roles],
        )

    try:
        payload = await verify_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing subject claim")

        # Try to find user in DB
        result = await db.execute(select(UserORM).where(UserORM.auth_subject == sub))
        user_orm = result.scalar_one_or_none()

        email = payload.get("email", f"{sub}@oidc.unknown")

        # JIT Provisioning (or just map for prototype)
        if not user_orm:
            if not settings.allow_jit_user_provisioning:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Authenticated identity is not provisioned",
                )
            user_orm = UserORM(auth_subject=sub, email=email)
            db.add(user_orm)
            await db.commit()
            await db.refresh(user_orm)

        # For prototype simplicity, if we JIT'd the user, we assume they need some roles.
        # In a real app we sync roles from token claims or IdP webhooks.
        raw_roles = payload.get("roles", [])
        if not isinstance(raw_roles, list):
            raise HTTPException(status_code=401, detail="Token roles claim is malformed")
        roles = [Role(r) for r in raw_roles]
        if x_driftguard_role:
            roles.append(Role(x_driftguard_role))
        if not roles:
            roles = [Role.VIEWER]

        tenant_claim = payload.get("tenant_id", payload.get("tid"))
        try:
            token_tenant_id = uuid.UUID(str(tenant_claim)) if tenant_claim else uuid.UUID(int=0)
        except ValueError:
            raise HTTPException(status_code=401, detail="Token tenant claim is malformed")

        return User(id=user_orm.id, tenant_id=token_tenant_id, email=email, roles=roles)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


async def get_current_tenant(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Derive tenant scope from a signed claim or an unambiguous membership."""
    if settings.auth_mode == "mock" and user.id == MOCK_USER.id:
        # Mock override
        return MOCK_TENANT

    stmt = (
        select(TenantMembershipORM, TenantORM)
        .join(TenantORM)
        .where(TenantMembershipORM.user_id == user.id, TenantORM.is_active.is_(True))
    )
    if user.tenant_id.int != 0:
        stmt = stmt.where(TenantMembershipORM.tenant_id == user.tenant_id)
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active tenant membership matches the authenticated identity",
        )
    if len(rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A signed tenant claim is required for multi-tenant identities",
        )

    membership, tenant_orm = rows[0]
    tenant_uuid = tenant_orm.id

    # Optional: set postgres runtime config for RLS
    # This requires an async context manager or engine-level hook, but we can do a local set:
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_uuid)},
        )

    # Merge roles (user roles + tenant specific roles)
    tenant_roles = [Role(r) for r in membership.roles_json]
    merged_roles = list(set([Role(r) for r in user.roles] + tenant_roles))
    user.roles = [Role(r) for r in merged_roles]
    user.tenant_id = tenant_uuid

    return Tenant(id=tenant_orm.id, name=tenant_orm.name)


def require_role(role: Role) -> Callable[[User], User]:
    """Dependency factory to enforce RBAC roles."""

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if role not in user.roles and Role.ADMIN not in user.roles:
            # Log authorization failure
            # For simplicity in synchronous dependency, we can't easily await db without it,
            # but we can log the exception.
            import structlog

            structlog.get_logger().error(
                "rbac_violation", user_id=str(user.id), required_role=role.value
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {role.value} role",
            )
        return user

    return role_checker


# ─── Common Request Dependencies ───────────────────────────────────────────────


class PaginationParams:
    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Items to skip"),
        limit: int = Query(50, ge=1, le=1000, description="Max items to return"),
    ):
        self.skip = skip
        self.limit = limit


def get_idempotency_key(
    x_idempotency_key: str | None = Header(None, description="Idempotency key for safe retries")
) -> str | None:
    if x_idempotency_key is None:
        return None
    normalized = x_idempotency_key.strip()
    if not normalized or len(normalized) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Idempotency-Key must contain 1 to 255 characters",
        )
    return normalized
