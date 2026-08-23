"""
DriftGuard-X v2 — Schema/Contract Tests (8 tests)

Validates all Pydantic v2 schemas for correctness, required fields,
validation errors, and serialization.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from packages.contracts.src.models import (
    AgentPipeline,
    ComponentType,
    ComponentVersion,
    ComponentVersionState,
    RecoveryCertificate,
    RequestRun,
    SpanRecord,
    Tenant,
    TraceArtifact,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─── Schema Tests ─────────────────────────────────────────────────────────────

@pytest.mark.contract
def test_tenant_valid() -> None:
    """Tenant schema accepts valid input."""
    t = Tenant(name="Acme Corp", slug="acme-corp")
    assert t.slug == "acme-corp"
    assert t.is_active is True
    assert isinstance(t.id, uuid.UUID)


@pytest.mark.contract
def test_tenant_slug_uppercase_rejected() -> None:
    """Tenant slug must be lowercase."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Tenant(name="Acme", slug="Acme")  # uppercase violates pattern


@pytest.mark.contract
def test_component_version_valid() -> None:
    """ComponentVersion schema with stable state."""
    cv = ComponentVersion(
        component_type=ComponentType.RETRIEVER,
        version_tag="v1",
        state=ComponentVersionState.STABLE,
        config_hash="a" * 64,
    )
    assert cv.component_type == ComponentType.RETRIEVER
    assert cv.version_tag == "v1"
    assert cv.state == ComponentVersionState.STABLE


@pytest.mark.contract
def test_agent_pipeline_duplicate_component_type_rejected() -> None:
    """AgentPipeline must not have duplicate component types."""
    import pydantic
    cv1 = ComponentVersion(
        component_type=ComponentType.RETRIEVER,
        version_tag="v1",
        config_hash="a" * 64,
    )
    cv2 = ComponentVersion(
        component_type=ComponentType.RETRIEVER,  # duplicate!
        version_tag="v2",
        config_hash="b" * 64,
    )
    tenant_id = uuid.uuid4()
    with pytest.raises(pydantic.ValidationError, match="Duplicate component type"):
        AgentPipeline(
            tenant_id=tenant_id,
            name="Bad Pipeline",
            version="1.0",
            component_versions=[cv1, cv2],
        )


@pytest.mark.contract
def test_span_record_end_before_start_rejected() -> None:
    """SpanRecord must reject end_time < start_time."""
    import pydantic
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    end = datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)  # before start!
    with pytest.raises(pydantic.ValidationError, match="end_time must be"):
        SpanRecord(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            start_time=start,
            end_time=end,
            tenant_id=uuid.uuid4(),
            pipeline_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
        )


@pytest.mark.contract
def test_request_run_reliability_out_of_range() -> None:
    """RequestRun reliability_score must be 0.0–1.0."""
    import pydantic
    with pytest.raises(pydantic.ValidationError, match="reliability_score"):
        RequestRun(
            tenant_id=uuid.uuid4(),
            pipeline_id=uuid.uuid4(),
            reliability_score=1.5,  # invalid!
        )


@pytest.mark.contract
def test_recovery_certificate_hash_computed() -> None:
    """RecoveryCertificate.compute_hash is deterministic."""
    run_id = uuid.uuid4()
    replay_id = uuid.uuid4()
    intervention_id = uuid.uuid4()
    issued_by = "demo-system"

    h1 = RecoveryCertificate.compute_hash(run_id, replay_id, intervention_id, issued_by)
    h2 = RecoveryCertificate.compute_hash(run_id, replay_id, intervention_id, issued_by)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


@pytest.mark.contract
def test_trace_artifact_get_root_span() -> None:
    """TraceArtifact.get_root_span returns the span with no parent."""
    run_id = uuid.uuid4()
    tid = uuid.uuid4()
    pid = uuid.uuid4()

    root = SpanRecord(
        trace_id="a" * 32,
        span_id="r" * 16,
        parent_span_id=None,  # root
        name="root",
        start_time=_utcnow(),
        tenant_id=tid,
        pipeline_id=pid,
        run_id=run_id,
    )
    child = SpanRecord(
        trace_id="a" * 32,
        span_id="c" * 16,
        parent_span_id="r" * 16,
        name="child",
        start_time=_utcnow(),
        tenant_id=tid,
        pipeline_id=pid,
        run_id=run_id,
    )
    trace = TraceArtifact(
        run_id=run_id,
        tenant_id=tid,
        pipeline_id=pid,
        spans=[root, child],
    )
    found_root = trace.get_root_span()
    assert found_root is not None
    assert found_root.span_id == "r" * 16
