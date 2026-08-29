from packages.contracts.src.models import SpanRecord
from packages.replay.src.time_authority import TrustedTimestampEnvelope

"""
DriftGuard-X v2 — E2E tests for RAEB Admissibility.
"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.contracts.src.models import (
    AdmissibilityScore,
    ComponentType,
    ReplayEpisode,
    ReplayStatus,
    TraceArtifact,
)
from packages.replay.src.raeb import RAEBGateway


def test_raeb_admissibility_fresh_and_deterministic():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)

    trace_id = uuid4()
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[SpanRecord(span_id=uuid4().hex[:16], trace_id=trace_id.hex, run_id=trace_id, tenant_id=uuid4(), pipeline_id=uuid4(), name="mock_span", parent_span_id=None, component_id="retriever_v1", component_type=ComponentType.RETRIEVER, start_time=datetime.now(UTC), end_time=datetime.now(UTC), inputs={}, outputs={}, status="OK")],

        created_at=datetime.now(UTC) - timedelta(minutes=5)
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

    current_time = datetime.now(UTC)
    evaluation = gateway.evaluate_admissibility(live_trace, proposed_replay, trusted_timestamp=TrustedTimestampEnvelope(timestamp=current_time, signature='mock', source='mock', issued_at=current_time, nonce='mock'), allow_uniform_prior=True)

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
        spans=[SpanRecord(span_id=uuid4().hex[:16], trace_id=trace_id.hex, run_id=trace_id, tenant_id=uuid4(), pipeline_id=uuid4(), name="mock_span", parent_span_id=None, component_id="retriever_v1", component_type=ComponentType.RETRIEVER, start_time=datetime.now(UTC), end_time=datetime.now(UTC), inputs={}, outputs={}, status="OK")],

        created_at=datetime.now(UTC) - timedelta(hours=2) # Very stale
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

    current_time = datetime.now(UTC)
    evaluation = gateway.evaluate_admissibility(live_trace, proposed_replay, trusted_timestamp=TrustedTimestampEnvelope(timestamp=current_time, signature='mock', source='mock', issued_at=current_time, nonce='mock'), allow_uniform_prior=True)

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
        spans=[SpanRecord(span_id=uuid4().hex[:16], trace_id=trace_id.hex, run_id=trace_id, tenant_id=uuid4(), pipeline_id=uuid4(), name="mock_span", parent_span_id=None, component_id="retriever_v1", component_type=ComponentType.RETRIEVER, start_time=datetime.now(UTC), end_time=datetime.now(UTC), inputs={}, outputs={}, status="OK")],

        created_at=datetime.now(UTC) + timedelta(minutes=5)
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

    current_time = datetime.now(UTC)
    with pytest.raises(ValueError, match="Negative age detected"):
        gateway.evaluate_admissibility(live_trace, proposed_replay, trusted_timestamp=TrustedTimestampEnvelope(timestamp=current_time, signature='mock', source='mock', issued_at=current_time, nonce='mock'), allow_uniform_prior=True)

def test_raeb_admissibility_naive_datetime():
    gateway = RAEBGateway(freshness_ttl_seconds=3600)
    trace_id = uuid4()

    # Trace created with naive datetime
    live_trace = TraceArtifact(
        run_id=trace_id,
        tenant_id=uuid4(),
        pipeline_id=uuid4(),
        spans=[SpanRecord(span_id=uuid4().hex[:16], trace_id=trace_id.hex, run_id=trace_id, tenant_id=uuid4(), pipeline_id=uuid4(), name="mock_span", parent_span_id=None, component_id="retriever_v1", component_type=ComponentType.RETRIEVER, start_time=datetime.now(UTC), end_time=datetime.now(UTC), inputs={}, outputs={}, status="OK")],

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

    current_time = datetime.now(UTC)
    with pytest.raises(ValueError, match="All timestamps must be timezone-aware"):
        gateway.evaluate_admissibility(live_trace, proposed_replay, trusted_timestamp=TrustedTimestampEnvelope(timestamp=current_time, signature='mock', source='mock', issued_at=current_time, nonce='mock'), allow_uniform_prior=True)

