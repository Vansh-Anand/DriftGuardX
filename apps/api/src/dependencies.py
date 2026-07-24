"""
DriftGuard-X v2 — FastAPI Dependencies
PRIVATE — All Rights Reserved.

Provides dependency injection for Tenant Isolation, RBAC, and Pagination.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Header, status
from packages.contracts.src.auth import User, Tenant, Role
from apps.api.src.auth.auth import MOCK_USER, MOCK_TENANT, oauth2_scheme, verify_token


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Verifies the JWT and returns the User object. Currently uses mock data."""
    if token == "mock-admin-token":
        return MOCK_USER
        
    try:
        # In a real app, we decode the token and fetch from DB
        payload = verify_token(token)
        # Mocking for prototype: assume any valid token is MOCK_USER
        return MOCK_USER
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


def get_current_tenant(user: User = Depends(get_current_user)) -> Tenant:
    """Extracts the tenant for the current user. Crucial for RLS / Isolation."""
    # In a real app, we verify the user belongs to the requested tenant
    # For prototype, we just return the mock tenant
    return MOCK_TENANT


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
    x_idempotency_key: Optional[str] = Header(None, description="Idempotency key for safe retries")
) -> Optional[str]:
    return x_idempotency_key
