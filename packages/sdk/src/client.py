"""
DriftGuard-X v2 — Typed Python SDK
PRIVATE — All Rights Reserved.

Provides a synchronous and asynchronous client for interacting with the DriftGuard-X API.
"""

from typing import Any
import httpx

from packages.contracts.src.sdk_models import FinalizeRunRequest, SpanIngestRequest, SpanIngestItem, BatchResult

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
        self._max_batch_size = 500

    def list_runs(self, skip: int = 0, limit: int = 20) -> dict[str, Any]:
        """List executed runs."""
        response = self.client.get("/runs", params={"skip": skip, "limit": limit})
        response.raise_for_status()
        return response.json()

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Get details for a specific run."""
        response = self.client.get(f"/runs/{run_id}")
        response.raise_for_status()
        return response.json()

    def create_replay(self, run_id: str, idempotency_key: str) -> dict[str, Any]:
        """Create a deterministic replay to test a counterfactual."""
        headers = self.headers.copy()
        headers["x-idempotency-key"] = idempotency_key
        response = self.client.post(f"/runs/{run_id}/replays", json={"seed": 42}, headers=headers)
        response.raise_for_status()
        return response.json()

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a running background job."""
        response = self.client.post(f"/jobs/{job_id}/cancel")
        response.raise_for_status()
        return response.json()

    def finalize_run(self, run_id: str, request: FinalizeRunRequest) -> dict[str, Any]:
        """Finalize a run with terminal status and telemetry."""
        payload = request.model_dump(exclude_unset=True)
        response = self.client.post(f"/runs/{run_id}/finalize", json=payload)
        response.raise_for_status()
        return response.json()

    def batch_spans(self, spans: list[dict[str, Any] | SpanIngestItem]) -> BatchResult:
        """Ingest a batch of spans using bounded chunking."""
        if not spans:
            return BatchResult(status="SUCCESS", ingested_count=0, skipped_count=0)
            
        total_ingested = 0
        total_skipped = 0
        all_errors = []
        failed_spans = []
        
        # Ensure we work with SpanIngestItem models
        processed_spans = []
        for s in spans:
            if isinstance(s, dict):
                processed_spans.append(SpanIngestItem(**s))
            else:
                processed_spans.append(s)
                
        # Chunk spans based on max batch size
        num_chunks = (len(processed_spans) + self._max_batch_size - 1) // self._max_batch_size
        failed_chunks = 0
        
        for i in range(0, len(processed_spans), self._max_batch_size):
            chunk = processed_spans[i : i + self._max_batch_size]
            request = SpanIngestRequest(spans=chunk)
            
            try:
                response = self.client.post(
                    "/ingest/spans", 
                    json=request.model_dump(exclude_unset=True)
                )
                response.raise_for_status()
                result = response.json()
                total_ingested += result.get("ingested", 0)
                total_skipped += result.get("skipped", 0)
                all_errors.extend(result.get("errors", []))
            except httpx.HTTPStatusError as e:
                failed_chunks += 1
                failed_spans.extend([s.span_id for s in chunk])
                all_errors.append(f"Batch rejected with status {e.response.status_code}: {e.response.text}")
            except Exception as e:
                failed_chunks += 1
                failed_spans.extend([s.span_id for s in chunk])
                all_errors.append(f"Network error during batching: {str(e)}")

        if failed_chunks == 0 and not all_errors:
            status = "SUCCESS"
        elif failed_chunks == num_chunks:
            status = "FAILURE"
        else:
            status = "PARTIAL_FAILURE"

        return BatchResult(
            status=status,
            ingested_count=total_ingested,
            skipped_count=total_skipped,
            failed_spans=failed_spans,
            errors=all_errors
        )


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
        self._max_batch_size = 500

    async def list_runs(self, skip: int = 0, limit: int = 20) -> dict[str, Any]:
        """List executed runs."""
        response = await self.client.get("/runs", params={"skip": skip, "limit": limit})
        response.raise_for_status()
        return response.json()

    async def finalize_run(self, run_id: str, request: FinalizeRunRequest) -> dict[str, Any]:
        """Finalize a run with terminal status and telemetry."""
        payload = request.model_dump(exclude_unset=True)
        response = await self.client.post(f"/runs/{run_id}/finalize", json=payload)
        response.raise_for_status()
        return response.json()

    async def batch_spans(self, spans: list[dict[str, Any] | SpanIngestItem]) -> BatchResult:
        """Ingest a batch of spans using bounded chunking."""
        if not spans:
            return BatchResult(status="SUCCESS", ingested_count=0, skipped_count=0)
            
        total_ingested = 0
        total_skipped = 0
        all_errors = []
        failed_spans = []
        
        processed_spans = []
        for s in spans:
            if isinstance(s, dict):
                processed_spans.append(SpanIngestItem(**s))
            else:
                processed_spans.append(s)
                
        num_chunks = (len(processed_spans) + self._max_batch_size - 1) // self._max_batch_size
        failed_chunks = 0
                
        for i in range(0, len(processed_spans), self._max_batch_size):
            chunk = processed_spans[i : i + self._max_batch_size]
            request = SpanIngestRequest(spans=chunk)
            
            try:
                response = await self.client.post(
                    "/ingest/spans", 
                    json=request.model_dump(exclude_unset=True)
                )
                response.raise_for_status()
                result = response.json()
                total_ingested += result.get("ingested", 0)
                total_skipped += result.get("skipped", 0)
                all_errors.extend(result.get("errors", []))
            except httpx.HTTPStatusError as e:
                failed_chunks += 1
                failed_spans.extend([s.span_id for s in chunk])
                all_errors.append(f"Batch rejected with status {e.response.status_code}: {e.response.text}")
            except Exception as e:
                failed_chunks += 1
                failed_spans.extend([s.span_id for s in chunk])
                all_errors.append(f"Network error during batching: {str(e)}")

        if failed_chunks == 0 and not all_errors:
            status = "SUCCESS"
        elif failed_chunks == num_chunks:
            status = "FAILURE"
        else:
            status = "PARTIAL_FAILURE"

        return BatchResult(
            status=status,
            ingested_count=total_ingested,
            skipped_count=total_skipped,
            failed_spans=failed_spans,
            errors=all_errors
        )
