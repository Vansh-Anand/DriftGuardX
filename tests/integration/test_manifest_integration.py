import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_replay_manifest_generation(client: AsyncClient):
    """Verify that creating a replay generates a manifest and returns its info."""

    # 1. Create a run with experimental retriever (which makes it synthetic)
    run_payload = {
        "query": "Integration test query",
        "use_experimental_retriever": True,
        "is_synthetic": True,
        "seed": 42,
    }
    run_resp = await client.post("/v1/runs", json=run_payload)
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # 2. Trigger a replay
    replay_payload = {
        "intervention": {
            "target_component": "retriever",
            "intervention_type": "rollback",
            "current_version": "v2-exp",
            "candidate_version": "v1",
        },
        "seed": 42,
    }
    replay_resp = await client.post(f"/v1/runs/{run_id}/replays", json=replay_payload)
    assert replay_resp.status_code == 201, replay_resp.text
    replay_data = replay_resp.json()

    # 3. Check for manifest fields
    assert replay_data["manifest_id"] is not None
    assert replay_data["manifest_hash"] is not None
    assert replay_data["is_pinned"] is True
    assert replay_data["evidence_class"] == "SYNTHETIC_SIMULATION"

    # 4. Fetch the replay directly to ensure it was persisted correctly
    replay_id = replay_data["id"]
    get_resp = await client.get(f"/v1/replays/{replay_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    assert get_data["manifest_id"] == replay_data["manifest_id"]
    assert get_data["manifest_hash"] == replay_data["manifest_hash"]
    assert get_data["is_pinned"] is True
    assert get_data["evidence_class"] == "SYNTHETIC_SIMULATION"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["seed", "missing_version"])
async def test_invalid_replay_returns_conflict_before_worker(client, monkeypatch, failure):
    import apps.api.src.routes.runs as runs_module
    import packages.replay.src.engine as engine_module
    from apps.api.src.pipeline.mock_rag import ALL_COMPONENT_VERSIONS
    from packages.contracts.src.models import ComponentType
    from packages.replay.src.engine import VersionRegistry

    response = await client.post(
        "/v1/runs",
        json={
            "query": "Replay preflight regression",
            "use_experimental_retriever": True,
            "is_synthetic": True,
            "seed": 42,
        },
    )
    assert response.status_code == 201
    run_id = response.json()["id"]
    if failure == "missing_version":
        registry = VersionRegistry()
        for version in ALL_COMPONENT_VERSIONS:
            if version.component_type == ComponentType.RETRIEVER:
                registry.register(version)
        monkeypatch.setattr(runs_module, "_build_version_registry", lambda: registry)

    def must_not_execute(*args, **kwargs):
        pytest.fail("Invalid API replay reached the worker")

    monkeypatch.setattr(engine_module, "_execute_component_isolated", must_not_execute)
    response = await client.post(
        f"/v1/runs/{run_id}/replays",
        json={
            "intervention": {
                "target_component": "retriever",
                "intervention_type": "rollback",
                "current_version": "v2-exp",
                "candidate_version": "v1",
            },
            "seed": 7 if failure == "seed" else 42,
        },
    )
    assert response.status_code == 409
    expected = "random seed" if failure == "seed" else "pinned component version"
    assert expected in response.json()["detail"]
