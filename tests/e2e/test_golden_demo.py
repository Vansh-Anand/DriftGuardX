"""
DriftGuard-X v2 — End-to-End Golden Demo Test (3 tests)
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


@pytest.mark.e2e
async def test_golden_demo_complete_trace(client: AsyncClient) -> None:
    """
    E2E: Execute experimental run, verify complete trace with span parentage.
    All spans must share trace_id. Root span has no parent.
    """
    # Create experimental run
    resp = await client.post(
        "/v1/runs",
        json={
            "query": "Latest AI safety guidelines?",
            "use_experimental_retriever": True,
            "seed": 42,
            "is_synthetic": True,
        },
    )
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    assert resp.json()["is_synthetic"] is True

    # Get trace
    trace_resp = await client.get(f"/v1/runs/{run_id}/trace")
    assert trace_resp.status_code == 200
    trace = trace_resp.json()

    assert trace["total_span_count"] >= 2, "Must have at least root + one component span"

    # All spans share same trace_id
    trace_ids = {s["trace_id"] for s in trace["spans"]}
    assert len(trace_ids) == 1, f"Expected single trace_id, got: {trace_ids}"

    # Root span has no parent
    root_spans = [s for s in trace["spans"] if not s.get("parent_span_id")]
    assert len(root_spans) == 1, f"Expected exactly one root span, got {len(root_spans)}"

    # All non-root spans reference a valid parent
    span_ids = {s["span_id"] for s in trace["spans"]}
    for span in trace["spans"]:
        if span.get("parent_span_id"):
            assert span["parent_span_id"] in span_ids, (
                f"Span {span['span_id']} references missing parent {span['parent_span_id']}"
            )


@pytest.mark.e2e
async def test_golden_demo_replay_with_pinned_versions(client: AsyncClient) -> None:
    """
    E2E: Create replay, verify only retriever version changes, improvement recorded.
    """
    # Create experimental run
    run_resp = await client.post(
        "/v1/runs",
        json={
            "query": "What is the AI safety framework?",
            "use_experimental_retriever": True,
            "seed": 42,
            "is_synthetic": True,
        },
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]
    original_score = run_resp.json()["reliability_score"]

    # Create replay
    replay_resp = await client.post(
        f"/v1/runs/{run_id}/replays",
        json={"swap_retriever_to_stable": True, "seed": 42},
    )
    assert replay_resp.status_code == 201, replay_resp.text
    replay = replay_resp.json()

    # Verify replay structure
    assert replay["original_run_id"] == run_id
    assert replay["status"] == "completed"
    assert replay["swapped_component_type"] == "retriever"
    assert replay["original_version_tag"] == "v2-exp"
    assert replay["replay_version_tag"] == "v1"
    assert replay["reliability_improvement"] is not None
    assert replay["reliability_improvement"] > 0, (
        f"Expected improvement > 0, got {replay['reliability_improvement']}"
    )

    # Verify by fetching replay
    get_resp = await client.get(f"/v1/replays/{replay['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == replay["id"]


@pytest.mark.e2e
async def test_golden_demo_intervention_not_auto_applied(client: AsyncClient) -> None:
    """
    E2E: Verify intervention is recorded but not auto-applied to production.
    Production state (pipeline config) must not change after replay.
    """
    # Create a run and replay
    run_resp = await client.post(
        "/v1/runs",
        json={
            "query": "Safety test",
            "use_experimental_retriever": True,
            "seed": 42,
            "is_synthetic": True,
        },
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    replay_resp = await client.post(
        f"/v1/runs/{run_id}/replays",
        json={"swap_retriever_to_stable": True, "seed": 42},
    )
    assert replay_resp.status_code == 201

    # Create another run — experimental pipeline must still be experimental
    # (intervention was not auto-applied)
    run_resp2 = await client.post(
        "/v1/runs",
        json={
            "query": "Safety test 2",
            "use_experimental_retriever": True,  # still using experimental
            "seed": 43,
            "is_synthetic": True,
        },
    )
    assert run_resp2.status_code == 201
    score2 = run_resp2.json()["reliability_score"]

    # Score should still be low (experimental retriever not replaced in prod)
    stable_resp = await client.post(
        "/v1/runs",
        json={"query": "Safety test 2", "use_experimental_retriever": False, "seed": 43, "is_synthetic": True},
    )
    stable_score = stable_resp.json()["reliability_score"]
    assert score2 < stable_score, (
        "Experimental pipeline should still return lower score — production state not mutated"
    )
