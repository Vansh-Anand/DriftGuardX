import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pagination_parameters(client: AsyncClient):
    """Verify that runs list supports skip and limit parameters."""
    headers = {"Authorization": "Bearer mock-admin-token"}

    # Check defaults
    response = await client.get("/v1/runs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 50

    # Check custom skip/limit
    response = await client.get("/v1/runs?skip=5&limit=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 10
    assert data["page"] == 1  # 5 // 10 + 1 = 1
