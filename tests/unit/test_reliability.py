"""
DriftGuard-X v2 — Reliability Evaluation Tests (3 tests)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from packages.contracts.src.models import SpanRecord, TraceArtifact
from packages.evaluation.src.reliability import (
    DEFAULT_CONFIG,
    aggregate_reliability_score,
    compute_reliability_delta,
    compute_reliability_vector,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_trace(
    *,
    latency_ms: float = 100.0,
    has_error: bool = False,
    policy_result: str = "allow",
    token_count: int = 100,
) -> TraceArtifact:
    tid = uuid.uuid4()
    pid = uuid.uuid4()
    run_id = uuid.uuid4()
    start = _utcnow()
    from datetime import timedelta
    end = datetime.now(timezone.utc)
    return TraceArtifact(
        run_id=run_id,
        tenant_id=tid,
        pipeline_id=pid,
        spans=[
            SpanRecord(
                trace_id="a" * 32,
                span_id="b" * 16,
                name="test",
                start_time=start,
                end_time=end,
                status_code="ERROR" if has_error else "OK",
                tenant_id=tid,
                pipeline_id=pid,
                run_id=run_id,
                latency_ms=latency_ms,
                policy_result=policy_result,
                token_count_input=token_count // 2,
                token_count_output=token_count // 2,
                error_type="TestError" if has_error else None,
            )
        ],
    )


@pytest.mark.unit
def test_reliability_vector_dimensions() -> None:
    """compute_reliability_vector returns all expected dimensions."""
    trace = _make_trace()
    vector = compute_reliability_vector(trace)
    for key in ["latency_ok", "policy_pass", "error_free", "token_budget", "faithfulness"]:
        assert key in vector, f"Missing dimension: {key}"
        assert 0.0 <= vector[key] <= 1.0, f"Out of range: {key}={vector[key]}"


@pytest.mark.unit
def test_error_reduces_reliability() -> None:
    """An errored span reduces the error_free dimension."""
    trace_ok = _make_trace(has_error=False)
    trace_err = _make_trace(has_error=True)
    vec_ok = compute_reliability_vector(trace_ok)
    vec_err = compute_reliability_vector(trace_err)
    assert vec_ok["error_free"] > vec_err["error_free"], "Error should reduce error_free score"


@pytest.mark.unit
def test_reliability_delta_computed_correctly() -> None:
    """compute_reliability_delta returns correct per-dimension differences."""
    before = {"a": 0.5, "b": 0.7}
    after = {"a": 0.8, "b": 0.6}
    delta = compute_reliability_delta(before, after)
    assert abs(delta["a"] - 0.3) < 1e-4
    assert abs(delta["b"] - (-0.1)) < 1e-4
