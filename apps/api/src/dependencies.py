"""
DriftGuard-X v2 — FastAPI Dependencies
PRIVATE — All Rights Reserved.

Provides dependency injection for Tenant Isolation, RBAC, and Pagination.
"""
import uuid

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.auth import MOCK_TENANT, MOCK_USER, oauth2_scheme, verify_token
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.models import TenantMembershipORM, TenantORM, UserORM
from packages.contracts.src.auth import Role, Tenant, User


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Verifies the JWT and returns the User object."""
    if settings.auth_mode == "mock" and token == "mock-admin-token":
        return MOCK_USER

    try:
        payload = verify_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing subject claim")

        # Try to find user in DB
        result = await db.execute(select(UserORM).where(UserORM.auth_subject == sub))
        user_orm = result.scalar_one_or_none()

        email = payload.get("email", f"{sub}@oidc.unknown")

        # JIT Provisioning (or just map for prototype)
        if not user_orm:
            user_orm = UserORM(auth_subject=sub, email=email)
            db.add(user_orm)
            await db.commit()
            await db.refresh(user_orm)

        # For prototype simplicity, if we JIT'd the user, we assume they need some roles.
        # In a real app we sync roles from token claims or IdP webhooks.
        roles = [Role(r) for r in payload.get("roles", [])]
        if not roles:
            roles = [Role.VIEWER]

        return User(id=user_orm.id, tenant_id=uuid.UUID(int=0), email=email, roles=roles) # tenant_id is placeholder here, resolved next

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e!s}",
        )


async def get_current_tenant(
    request: Request,
    user: User = Depends(get_current_user),
    x_tenant_id: str | None = Header(None, description="Explicit Tenant ID"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """Extracts and verifies the tenant for the current user. Crucial for RLS / Isolation."""
    if settings.auth_mode == "mock" and user.id == MOCK_USER.id:
        # Mock override
        return MOCK_TENANT

    if not x_tenant_id:
        # In a real app we might default to their only tenant, but for security
        # it's best to require the client to specify.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required"
        )

    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-ID format"
        )

    # Check membership
    result = await db.execute(
        select(TenantMembershipORM, TenantORM)
        .join(TenantORM)
        .where(
            TenantMembershipORM.user_id == user.id,
            TenantMembershipORM.tenant_id == tenant_uuid
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this tenant or tenant does not exist"
        )

    membership, tenant_orm = row

    # Optional: set postgres runtime config for RLS
    # This requires an async context manager or engine-level hook, but we can do a local set:
    await db.execute(f"SET LOCAL app.current_tenant_id = '{tenant_uuid!s}'")

    # Merge roles (user roles + tenant specific roles)
    tenant_roles = [Role(r) for r in membership.roles_json]
    merged_roles = list(set(user.roles + tenant_roles))
    user.roles = merged_roles
    user.tenant_id = tenant_uuid

    return Tenant(id=tenant_orm.id, name=tenant_orm.name)


def require_role(role: Role):
    """Dependency factory to enforce RBAC roles."""
    def role_checker(user: User = Depends(get_current_user)):
        if role not in user.roles and Role.ADMIN not in user.roles:
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
    return x_idempotency_key
