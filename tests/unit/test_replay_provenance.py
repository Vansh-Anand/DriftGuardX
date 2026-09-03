import packages.contracts.src.models
import pytest
import uuid
from datetime import datetime, UTC

from packages.contracts.src.evidence import RecoveryEvidenceKind
from packages.contracts.src.models import (
    ComponentType,
    ComponentVersion,
    RequestRun,
    TraceArtifact,
    ReplayStateManifest,
)
from packages.contracts.src.recovery_models import InterventionSpec
from packages.contracts.src.bcrb_models import BCRBCandidate, InterventionType
from packages.replay.src.engine import ReplayEngine, VersionRegistry, MockRetrieverV1
from packages.replay.src.test_framework import CanaryTestFramework


@pytest.mark.asyncio
async def test_synthetic_executor_yields_synthetic_demo_provenance():
    # 1. Setup Version Registry with Mock executor
    registry = VersionRegistry()
    mock_version = ComponentVersion(
        id=uuid.uuid4(),
        component_type=ComponentType.RETRIEVER,
        version_tag="v1",
        config_hash="test-config-hash"
    )
    registry.register(mock_version)
    
    engine = ReplayEngine(registry)

    # 2. Setup original run and trace
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    original_run = RequestRun(
        id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        is_synthetic=False
    )
    original_trace = TraceArtifact(
        run_id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        spans=[],
    )
    
    manifest = ReplayStateManifest(
        run_id=run_id,
        tenant_id=tenant_id,
        original_query="What is DriftGuardX?",
        original_query_hash="hash",
        corpus_version_id="corpus",
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="config",
        prompt_template_hash="prompt",
        retriever_version="v1",
        retriever_settings={"top_k": 3},
        retrieved_chunk_ids=["chunk1"],
        embedding_model_version="v1",
        vector_index_snapshot_id="v1",
        tool_schemas_hash="tool",
        policy_config_hash="policy",
        memory_snapshot_id="mem",
        random_seed=42,
        container_image_digest="digest",
        dependency_lockfile_hash="deps",
        trace_root_hash="trace"
    )
    
    intervention = InterventionSpec(
        target_component=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ALTERNATE_STABLE,
        current_version="v0",
        candidate_version="v1"
    )
    
    # 3. Execute
    episode, trace = engine.execute_replay(
        original_run=original_run,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=mock_version,
        original_reliability_vector={},
        manifest=manifest
    )
    
    # 4. Assert
    assert episode.is_synthetic is True
    assert episode.evidence_kind == RecoveryEvidenceKind.SYNTHETIC_DEMO


@pytest.mark.asyncio
async def test_bcrb_rejects_synthetic_evidence(monkeypatch):
    # Setup test framework
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    
    # Create candidate
    candidate = BCRBCandidate(
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ALTERNATE_STABLE,
    )
    
    # Mock DB query results
    class MockResult:
        def __init__(self, data):
            self.data = data
        def scalar_one_or_none(self):
            return self.data
            
    class MockORM:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
                
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    
    mock_manifest = MockORM(
        id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=tenant_id,
        original_query="query",
        original_query_hash="hash",
        corpus_version_id="corpus",
        model_provider="openai",
        model_identifier="gpt-4",
        model_config_hash="config",
        prompt_template_hash="prompt",
        retriever_version="v1",
        retriever_settings={"top_k": 3},
        retrieved_chunk_ids=["chunk1"],
        embedding_model_version="v1",
        vector_index_snapshot_id="v1",
        tool_schemas_hash="tool",
        policy_config_hash="policy",
        memory_snapshot_id="mem",
        random_seed=42,
        generation_parameters={},
        container_image_digest="digest",
        dependency_lockfile_hash="deps",
        trace_root_hash="trace",
        manifest_hash="manifest"
    )
    
    mock_run = MockORM(
        id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        trace_id="trace",
        status=packages.contracts.src.models.RunStatus.COMPLETED,
        created_at=datetime.now(UTC),
        duration_ms=100.0,
        error_message=None,
        reliability_vector={},
        is_synthetic=False
    )
    
    mock_trace = MockORM(
        id=uuid.uuid4(),
        run_id=run_id,
        payload={},
        payload_hash="hash",
        created_at=datetime.now(UTC)
    )
    
    # Mock db.execute
    class MockDB:
        def __init__(self):
            self.call_count = 0
        async def execute(self, stmt):
            self.call_count += 1
            if self.call_count == 1:
                return MockResult(mock_manifest)
            elif self.call_count == 2:
                return MockResult(mock_run)
            elif self.call_count == 3:
                return MockResult(mock_trace)
            return MockResult(None)
            
    # Mock ReplayEngine to return SYNTHETIC_DEMO
    class MockEpisode:
        replay_id = uuid.uuid4()
        cost_usd = 0.0
        reliability_vector = {}
        evidence_kind = RecoveryEvidenceKind.SYNTHETIC_DEMO
        is_synthetic = True
        
    monkeypatch.setattr("packages.replay.src.engine.ReplayEngine.execute_replay", lambda *args, **kwargs: (MockEpisode(), None))
    
    # Execute
    step = await framework.execute_canary(
        candidate=candidate,
        original_run_id=str(run_id),
        session_id=str(uuid.uuid4()),
        db=MockDB()
    )
    
    # Assert BCRB rejects it
    assert step.status == "failed"
    assert "SYNTHETIC_EVIDENCE_ONLY" in step.decision_reason
    assert candidate.causal_evidence.evidence_provenance == RecoveryEvidenceKind.SYNTHETIC_DEMO
