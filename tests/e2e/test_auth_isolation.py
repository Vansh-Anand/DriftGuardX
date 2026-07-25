import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.src.main import app

@pytest.mark.asyncio
async def test_auth_rejection(client: AsyncClient):
    """Verify endpoints reject requests without a token."""
    client.headers.pop("Authorization", None)
    response = await client.get("/v1/runs")
    # Should be unauthorized without token
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_auth_acceptance(client: AsyncClient):
    """Verify mock auth token allows access."""
    response = await client.get("/v1/runs")
    # Should be successful
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data

@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    """Verify invalid token is rejected."""
    client.headers["Authorization"] = "Bearer invalid-token"
    response = await client.get("/v1/runs")
    # Should be unauthorized
    assert response.status_code == 401
