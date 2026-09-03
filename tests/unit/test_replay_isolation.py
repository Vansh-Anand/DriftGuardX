"""
DriftGuard-X v2 — Replay Isolation Tests (4 tests)

Verifies that replays only swap exactly one component version
and pin all other versions to the original run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from apps.api.src.pipeline.mock_rag import (
    ALL_COMPONENT_VERSIONS,
    PIPELINE_WITH_EXPERIMENTAL_RETRIEVER,
    RETRIEVER_V1,
    RETRIEVER_V2_EXP,
    MockRAGPipeline,
)
from packages.contracts.src.models import (
    ComponentType,
    ComponentType,
    InterventionType,
    ReplayStateManifest,
    RequestRun,
    TraceArtifact,
)
from packages.replay.src.engine import (
    ReplayEngine,
    VersionRegistry,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_fully_pinned_manifest(run_id, tenant_id) -> ReplayStateManifest:
    return ReplayStateManifest(
        run_id=run_id,
        tenant_id=tenant_id,
        original_query="test query",
        original_query_hash="query-hash",
        corpus_version_id="corpus-v1",
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="abc",
        prompt_template_hash="def",
        retriever_version="v1",
        retriever_settings={"k": 5},
        retrieved_chunk_ids=["chunk1"],
        embedding_model_version="v2",
        vector_index_snapshot_id="snapshot-1",
        tool_schemas_hash="tool-hash",
        policy_config_hash="policy-hash",
        memory_snapshot_id="memory-1",
        random_seed=42,
        container_image_digest="sha256:123",
        dependency_lockfile_hash="lock-hash",
        trace_root_hash="trace-hash",
    )


def _make_registry() -> VersionRegistry:
    registry = VersionRegistry()
    for cv in ALL_COMPONENT_VERSIONS:
        registry.register(cv)
    return registry


def _make_original_run_and_trace() -> tuple[RequestRun, TraceArtifact]:
    """Execute the experimental pipeline to get original run + trace."""
    run_id = uuid.uuid4()
    pipeline = MockRAGPipeline(PIPELINE_WITH_EXPERIMENTAL_RETRIEVER)
    run, trace = pipeline.execute(run_id=run_id, query="test query", seed=42, is_synthetic=True)
    return run, trace


@pytest.mark.unit
def test_replay_only_swaps_one_component() -> None:
    """The replay must swap only the retriever; all other versions must be pinned."""
    original_run, original_trace = _make_original_run_and_trace()

    from packages.contracts.src.recovery_models import InterventionSpec
    intervention = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        current_version=RETRIEVER_V2_EXP.version_tag,
        candidate_version=RETRIEVER_V1.version_tag,
        rollback_plan="Stale evidence detected",
    )

    engine = ReplayEngine(_make_registry())
    manifest = _make_fully_pinned_manifest(original_run.id, original_run.tenant_id)
    episode, replay_trace = engine.execute_replay(
        original_run=original_run,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=RETRIEVER_V1,
        original_reliability_vector=original_run.reliability_vector or {},
        seed=42,
        manifest=manifest,
    )

    # Check: retriever version in replay trace must be v1 (stable)
    retriever_spans = [s for s in replay_trace.spans if s.component_type == ComponentType.RETRIEVER]
    assert len(retriever_spans) > 0, "No retriever span found in replay"
    for span in retriever_spans:
        assert (
            span.component_version_tag == "v1"
        ), f"Expected retriever v1 in replay, got {span.component_version_tag}"


@pytest.mark.unit
def test_replay_pins_non_swapped_versions() -> None:
    """Non-intervened components in the replay must match original versions."""
    original_run, original_trace = _make_original_run_and_trace()

    from packages.contracts.src.recovery_models import InterventionSpec
    intervention = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        current_version=RETRIEVER_V2_EXP.version_tag,
        candidate_version=RETRIEVER_V1.version_tag,
        rollback_plan="Stale evidence detected",
    )

    engine = ReplayEngine(_make_registry())
    manifest = _make_fully_pinned_manifest(original_run.id, original_run.tenant_id)
    episode, replay_trace = engine.execute_replay(
        original_run=original_run,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=RETRIEVER_V1,
        original_reliability_vector=original_run.reliability_vector or {},
        seed=42,
        manifest=manifest,
    )

    # Generator, reranker must still be v1 in replay
    for span in replay_trace.spans:
        if span.component_type in (ComponentType.GENERATOR, ComponentType.RERANKER):
            assert (
                span.component_version_tag == "v1"
            ), f"{span.component_type} version changed unexpectedly in replay"


@pytest.mark.unit
def test_replay_improves_reliability_over_experimental() -> None:
    """Reliability score should improve when swapping from experimental to stable retriever."""
    original_run, original_trace = _make_original_run_and_trace()

    from packages.contracts.src.recovery_models import InterventionSpec
    intervention = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        current_version=RETRIEVER_V2_EXP.version_tag,
        candidate_version=RETRIEVER_V1.version_tag,
        rollback_plan="test",
    )

    engine = ReplayEngine(_make_registry())

    manifest = _make_fully_pinned_manifest(original_run.id, original_run.tenant_id)
    episode, _ = engine.execute_replay(
        original_run=original_run,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=RETRIEVER_V1,
        original_reliability_vector=original_run.reliability_vector or {},
        seed=42,
        manifest=manifest,
    )

    assert episode.reliability_improvement is not None
    assert (
        episode.reliability_improvement > 0
    ), f"Expected positive improvement, got {episode.reliability_improvement}"


@pytest.mark.unit
def test_replay_episode_has_correct_version_ids() -> None:
    """ReplayEpisode must record original and replay version IDs correctly."""
    original_run, original_trace = _make_original_run_and_trace()

    from packages.contracts.src.recovery_models import InterventionSpec
    intervention = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        current_version=RETRIEVER_V2_EXP.version_tag,
        candidate_version=RETRIEVER_V1.version_tag,
        rollback_plan="test",
    )

    engine = ReplayEngine(_make_registry())

    manifest = _make_fully_pinned_manifest(original_run.id, original_run.tenant_id)
    episode, _ = engine.execute_replay(
        original_run=original_run,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=RETRIEVER_V1,
        original_reliability_vector=original_run.reliability_vector or {},
        seed=42,
        manifest=manifest,
    )

    assert episode.original_version_id == RETRIEVER_V2_EXP.id
    assert episode.replay_version_id == RETRIEVER_V1.id
    assert episode.original_version_tag == "v2-exp"
    assert episode.replay_version_tag == "v1"
    assert episode.swapped_component_type == ComponentType.RETRIEVER
