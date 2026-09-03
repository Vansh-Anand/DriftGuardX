import uuid

import jwt
import pytest
from httpx import AsyncClient

from apps.api.src.auth.auth import (
    MOCK_JWT_SECRET,
    MOCK_TENANT_ID,
)
from packages.contracts.src.auth import Role

# Generate a mock valid token for a fake user
FAKE_TENANT_ID = "11111111-1111-1111-1111-111111111111"
FAKE_USER_ID = "22222222-2222-2222-2222-222222222222"


def generate_mock_jwt(sub=FAKE_USER_ID, email="test@test.com", roles=None):
    if roles is None:
        roles = ["VIEWER"]
    payload = {"sub": sub, "email": email, "roles": roles}
    return jwt.encode(payload, MOCK_JWT_SECRET, algorithm="HS256")


# Test 1: Cross-tenant read/write (IDOR attempt)
@pytest.mark.asyncio
async def test_cross_tenant_access_denied(client: AsyncClient):
    # A user trying to access a tenant they aren't a member of.
    # Note: In development mode, the token 'mock-admin-token' is automatically mapped to MOCK_TENANT.

    # We will use the FAKE_TENANT_ID header, but with the 'mock-admin-token'
    # The 'mock-admin-token' bypasses membership checks in the prototype
    # Let's use a standard encoded JWT for our fake user.
    token = generate_mock_jwt()

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(MOCK_TENANT_ID),  # Trying to access MOCK_TENANT
    }

    # The user should be JIT created, but they won't have membership to MOCK_TENANT
    response = await client.get("/v1/runs", headers=headers)
    assert response.status_code in (401, 403)


# Test 2: Invalid Tokens
@pytest.mark.asyncio
async def test_invalid_token(client: AsyncClient):
    headers = {"Authorization": "Bearer invalid_jwt_token_here", "X-Tenant-ID": str(MOCK_TENANT_ID)}

    response = await client.get("/v1/runs", headers=headers)
    assert response.status_code == 401
    assert response.status_code == 401


# Test 3: Role escalation
@pytest.mark.asyncio
async def test_role_escalation():
    # Fake user has only VIEWER role.
    # Create a tenant and membership directly in DB is hard via HTTP without a test fixture,
    # but we can try an admin route and expect 403 on the role requirement.

    # Even if they had tenant access, they don't have ADMIN role.
    # We can test by bypassing the tenant check or letting it fail at the role level.
    # We'll just verify the role checker itself.

    from apps.api.src.dependencies import require_role
    from packages.contracts.src.auth import User

    checker = require_role(Role.ADMIN)
    viewer_user = User(id=uuid.uuid4(), tenant_id=uuid.uuid4(), email="viewer", roles=[Role.VIEWER])

    import fastapi

    with pytest.raises(fastapi.HTTPException) as exc:
        checker(viewer_user)

    assert exc.value.status_code == 403
    assert "requires admin role" in exc.value.detail.lower()


# Test 4: Tenant is derived from signed identity/membership, never a client header
@pytest.mark.asyncio
async def test_missing_tenant_header(client: AsyncClient):
    token = generate_mock_jwt()
    headers = {
        "Authorization": f"Bearer {token}"
        # No signed tenant claim and no provisioned membership.
    }

    response = await client.get("/v1/runs", headers=headers)
    assert response.status_code in (401, 403)


# Test 5: Valid mock admin fallback
@pytest.mark.asyncio
async def test_valid_mock_admin(client: AsyncClient):
    headers = {"Authorization": "Bearer mock-admin-token", "X-Tenant-ID": str(MOCK_TENANT_ID)}

    response = await client.get("/v1/runs", headers=headers)
    # The mock-admin-token bypasses membership check in development
    assert response.status_code == 200


# Test 6: Tenant isolation in idempotency key (Logic check)
@pytest.mark.asyncio
async def test_idempotency_key_scoping():
    from apps.api.src.models import IdempotencyKeyORM

    # Ensure the unique constraint exists for (tenant_id, key)
    assert any(
        c.name == "uq_idempotency_tenant_key"
        for c in IdempotencyKeyORM.__table_args__
        if hasattr(c, "name")
    )
