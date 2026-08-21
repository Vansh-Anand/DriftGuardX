"""
DriftGuard-X v2 — E2E tests for RAEB Admissibility.
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from packages.replay.src.raeb import RAEBGateway
from packages.contracts.src.models import (
    TraceArtifact,
    ReplayEpisode,
    AdmissibilityScore,
    ComponentType,
    ReplayStatus
)

def test_raeb_admissibility_fresh_and_deterministic():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)
    
    trace_id = uuid4()
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[],
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    
    proposed_replay = ReplayEpisode(
        tenant_id=uuid4(),
        run_id=trace_id,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid4(),
        replay_version_id=uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        status=ReplayStatus.PENDING
    )
    
    current_time = datetime.now(timezone.utc)
    evaluation = gateway.evaluate_admissibility(live_trace, proposed_replay, current_time=current_time)
    
    assert evaluation.admissibility == AdmissibilityScore.ADMISSIBLE
    assert evaluation.equivalence_vector.freshness_score > 0.9
    assert evaluation.information_gain_estimate >= 0.0

def test_raeb_admissibility_stale_trace():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)
    
    trace_id = uuid4()
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[],
        created_at=datetime.now(timezone.utc) - timedelta(hours=2) # Very stale
    )
    
    proposed_replay = ReplayEpisode(
        tenant_id=uuid4(),
        run_id=trace_id,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid4(),
        replay_version_id=uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        status=ReplayStatus.PENDING
    )
    
    current_time = datetime.now(timezone.utc)
    evaluation = gateway.evaluate_admissibility(live_trace, proposed_replay, current_time=current_time)
    
    # Should be rejected because it's too old
    assert evaluation.admissibility == AdmissibilityScore.UNSUPPORTED
    assert evaluation.equivalence_vector.freshness_score == 0.0
    
def test_raeb_admissibility_negative_age():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)
    trace_id = uuid4()
    
    # Trace created in the future relative to current_time
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[],
        created_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    
    proposed_replay = ReplayEpisode(
        tenant_id=uuid4(),
        run_id=trace_id,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid4(),
        replay_version_id=uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        status=ReplayStatus.PENDING
    )
    
    current_time = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="Negative age detected"):
        gateway.evaluate_admissibility(live_trace, proposed_replay, current_time=current_time)

def test_raeb_admissibility_naive_datetime():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)
    trace_id = uuid4()
    
    # Trace created with naive datetime
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[],
        created_at=datetime.now() # Naive
    )
    
    proposed_replay = ReplayEpisode(
        tenant_id=uuid4(),
        run_id=trace_id,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid4(),
        replay_version_id=uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        status=ReplayStatus.PENDING
    )
    
    current_time = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="All timestamps must be timezone-aware"):
        gateway.evaluate_admissibility(live_trace, proposed_replay, current_time=current_time)

