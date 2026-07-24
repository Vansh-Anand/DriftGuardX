"""
DriftGuard-X v2 — Typed Python SDK
PRIVATE — All Rights Reserved.

Provides a synchronous and asynchronous client for interacting with the DriftGuard-X API.
"""
import os
from typing import Dict, Any, Optional

import httpx


class DriftGuardClient:
    """Synchronous client for DriftGuard-X API."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(base_url=self.base_url, headers=self.headers)

    def list_runs(self, skip: int = 0, limit: int = 20) -> Dict[str, Any]:
        """List executed runs."""
        response = self.client.get("/runs", params={"skip": skip, "limit": limit})
        response.raise_for_status()
        return response.json()

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get details for a specific run."""
        response = self.client.get(f"/runs/{run_id}")
        response.raise_for_status()
        return response.json()

    def create_replay(self, run_id: str, idempotency_key: str) -> Dict[str, Any]:
        """Create a deterministic replay to test a counterfactual."""
        headers = self.headers.copy()
        headers["x-idempotency-key"] = idempotency_key
        response = self.client.post(f"/runs/{run_id}/replays", json={"seed": 42}, headers=headers)
        response.raise_for_status()
        return response.json()

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running background job."""
        response = self.client.post(f"/jobs/{job_id}/cancel")
        response.raise_for_status()
        return response.json()


class AsyncDriftGuardClient:
    """Asynchronous client for DriftGuard-X API."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers)

    async def list_runs(self, skip: int = 0, limit: int = 20) -> Dict[str, Any]:
        """List executed runs."""
        response = await self.client.get("/runs", params={"skip": skip, "limit": limit})
        response.raise_for_status()
        return response.json()
