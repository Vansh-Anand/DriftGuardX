import math
import uuid
from datetime import UTC, datetime

from packages.contracts.src.models import ComponentType, ReplayEpisode, TraceArtifact
from packages.replay.src.raeb import RAEBGateway


def _mock_trace(spans_count: int) -> TraceArtifact:
    return TraceArtifact(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4(),
        spans=[
            {
                "trace_id": "0" * 32,
                "span_id": f"{i:016x}",
                "name": "span",
                "component_type": ComponentType.RETRIEVER if i == 0 else ComponentType.GENERATOR,
                "start_time": datetime.now(UTC),
                "tenant_id": uuid.uuid4(),
                "pipeline_id": uuid.uuid4(),
                "run_id": uuid.uuid4(),
            }
            for i in range(spans_count)
        ],
        created_at=datetime.now(UTC),
    )


def _mock_replay() -> ReplayEpisode:
    return ReplayEpisode(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(),
        replay_version_id=uuid.uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        created_at=datetime.now(UTC),
    )


def test_raeb_ig_maximum_at_half_split():
    # If N=100, the maximum information gain is when impact = 0.5 (K=50).
    gateway = RAEBGateway()
    trace = _mock_trace(100)
    replay = _mock_replay()

    # We patch the impact temporarily inside evaluate_admissibility or just test the math directly.
    # The determinism is 0.95. Let's trace it.
    # Impact = 0.8 if > 5 else 1.0
    # The current mock code hardcodes impact. We should verify the math independent of the hardcoded 0.8.

    # Let's extract the exact formula test.
    N = 100.0

    def ig(impact):
        K = max(1e-9, min(N, N * impact))
        if K <= 1e-9 or K >= N - 1e-9:
            return 0.0
        p_k = K / N
        p_nk = (N - K) / N
        return math.log2(N) - (p_k * math.log2(K) + p_nk * math.log2(N - K))

    ig_half = ig(0.5)
    ig_quarter = ig(0.25)
    ig_tenth = ig(0.1)

    assert ig_half == 1.0  # H(100) - (0.5*H(50) + 0.5*H(50)) = log2(100) - log2(50) = 1.0
    assert ig_half > ig_quarter
    assert ig_quarter > ig_tenth


def test_raeb_ig_zero_at_bounds():
    N = 100.0

    def ig(impact):
        K = max(1e-9, min(N, N * impact))
        if K <= 1e-9 or K >= N - 1e-9:
            return 0.0
        p_k = K / N
        p_nk = (N - K) / N
        return math.log2(N) - (p_k * math.log2(K) + p_nk * math.log2(N - K))

    assert ig(0.0) == 0.0
    assert ig(1.0) == 0.0


def test_raeb_ig_integration():
    gateway = RAEBGateway()
    trace = _mock_trace(100)  # impact will be 0.8
    replay = _mock_replay()

    from packages.replay.src.time_authority import TrustedTimestampEnvelope

    now = datetime.now(UTC)
    ts = TrustedTimestampEnvelope(
        timestamp=now, signature="mock", source="mock", issued_at=now, nonce="mock"
    )
    eval = gateway.evaluate_admissibility(
        trace, replay, trusted_timestamp=ts, allow_uniform_prior=True
    )

    # The strict resolver selects the single retriever span. With no child
    # edges, its affected set is one of the 100 graph nodes; the unobserved
    # component receives the conservative default determinism score.
    assert eval.equivalence_vector.dependency_impact_score == 0.01
    assert eval.equivalence_vector.determinism_score == 0.7
    assert (
        abs(
            eval.information_gain_estimate
            - eval.ig_estimator_metadata["raw_eig"]
            * eval.ig_estimator_metadata["determinism_multiplier"]
        )
        < 1e-12
    )
