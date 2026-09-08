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
        embedding_provider="test_provider",
        embedding_model_id="test_model_id",
        embedding_model_version="v2",
        embedding_vector_dimension=128,
        embedding_config_hash="test_config_hash",
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
    run, trace = pipeline.execute(
        run_id=run_id, query="test query", seed=42, evidence_class="SYNTHETIC_SIMULATION"
    )
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


@pytest.mark.parametrize(
    "fault",
    [
        "manifest_tenant",
        "manifest_run",
        "manifest_content",
        "manifest_seed",
        "trace_tenant",
        "trace_run",
        "trace_pipeline",
        "span_tenant",
        "missing_version",
        "unregistered_version",
        "wrong_registered_type",
        "wrong_registered_tag",
        "wrong_replacement_type",
        "wrong_replacement_tag",
        "conflicting_versions",
        "wrong_original_tag",
        "missing_original_tag",
    ],
)
def test_invalid_replay_bindings_refused_before_execution(fault, monkeypatch):
    import packages.replay.src.engine as engine_module
    from packages.contracts.src.recovery_models import InterventionSpec

    run, trace = _make_original_run_and_trace()
    manifest = _make_fully_pinned_manifest(run.id, run.tenant_id)
    registry = _make_registry()
    replacement = RETRIEVER_V1
    preserved = next(
        s for s in trace.spans if s.component_type and s.component_type != ComponentType.RETRIEVER
    )
    if fault == "manifest_tenant":
        manifest.tenant_id = uuid.uuid4()
    elif fault == "manifest_run":
        manifest.run_id = uuid.uuid4()
    elif fault == "manifest_content":
        manifest.retriever_settings["k"] = 99
    elif fault == "manifest_seed":
        manifest.random_seed = 7
        manifest.manifest_hash = manifest.compute_hash()
    elif fault == "trace_tenant":
        trace.tenant_id = uuid.uuid4()
    elif fault == "trace_run":
        trace.run_id = uuid.uuid4()
    elif fault == "trace_pipeline":
        trace.pipeline_id = uuid.uuid4()
    elif fault == "span_tenant":
        preserved.tenant_id = uuid.uuid4()
    elif fault == "missing_version":
        preserved.component_version_id = None
    elif fault == "unregistered_version":
        preserved.component_version_id = uuid.uuid4()
    elif fault in ("wrong_registered_type", "wrong_registered_tag"):
        version = registry.get(preserved.component_version_id)
        changes = (
            {"component_type": ComponentType.RETRIEVER}
            if fault == "wrong_registered_type"
            else {"version_tag": "unrecorded"}
        )
        registry.register(version.model_copy(update=changes))
    elif fault == "wrong_replacement_type":
        replacement = replacement.model_copy(update={"component_type": ComponentType.GENERATOR})
    elif fault == "wrong_replacement_tag":
        replacement = replacement.model_copy(update={"version_tag": "unrecorded"})
    elif fault == "conflicting_versions":
        version = registry.get(preserved.component_version_id).model_copy(
            update={"id": uuid.uuid4()}
        )
        registry.register(version)
        trace.spans.append(preserved.model_copy(update={"component_version_id": version.id}))

    def must_not_execute(*args, **kwargs):
        pytest.fail("Invalid replay bindings reached component execution")

    monkeypatch.setattr(engine_module, "_execute_component_isolated", must_not_execute)
    with pytest.raises(ValueError, match="Replay refused"):
        ReplayEngine(registry).execute_replay(
            original_run=run,
            original_trace=trace,
            intervention=InterventionSpec(
                target_component=ComponentType.RETRIEVER,
                intervention_type=InterventionType.ROLLBACK,
                current_version=(
                    None if fault == "missing_original_tag" else
                    "unrecorded" if fault == "wrong_original_tag" else RETRIEVER_V2_EXP.version_tag
                ),
                candidate_version=RETRIEVER_V1.version_tag,
            ),
            replay_version=replacement,
            original_reliability_vector={},
            manifest=manifest,
        )
