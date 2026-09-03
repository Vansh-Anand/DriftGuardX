"""
DriftGuard-X v2 — Trace Parentage Tests (4 tests)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from packages.contracts.src.models import SpanRecord, TraceArtifact
from packages.trace_sdk.src.tracer import TraceContext


def _utcnow() -> datetime:
    return datetime.now(UTC)


@pytest.mark.unit
def test_all_spans_have_trace_id() -> None:
    """All spans in a trace share the same trace_id."""
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(tenant_id=tenant_id, pipeline_id=pipeline_id, run_id=run_id)
    trace_id = ctx.trace_id

    # Build root + 2 child spans
    root_builder = ctx.start_span("root")
    root_builder.finish()
    root_span = root_builder.build()
    ctx.record_span(root_span)

    child_builder = ctx.start_span("child", parent_span_id=root_span.span_id)
    child_builder.finish()
    child_span = child_builder.build()
    ctx.record_span(child_span)

    for span in ctx.get_spans():
        assert span.trace_id == trace_id, f"Span {span.span_id} has wrong trace_id"


@pytest.mark.unit
def test_root_span_has_no_parent() -> None:
    """The root span must have parent_span_id = None."""
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(tenant_id=tenant_id, pipeline_id=pipeline_id, run_id=run_id)
    root_builder = ctx.start_span("root")
    assert root_builder._parent_span_id is None


@pytest.mark.unit
def test_child_span_references_parent() -> None:
    """Child span must reference its parent span_id."""
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(tenant_id=tenant_id, pipeline_id=pipeline_id, run_id=run_id)
    root_builder = ctx.start_span("root")
    root_builder.finish()
    root_span = root_builder.build()
    ctx.record_span(root_span)

    child_builder = ctx.start_span("child", parent_span_id=root_span.span_id)
    child_builder.finish()
    child_span = child_builder.build()

    assert child_span.parent_span_id == root_span.span_id


@pytest.mark.unit
def test_orphan_detection() -> None:
    """TraceArtifact.get_span_chain returns empty for unknown span_id."""
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    root = SpanRecord(
        trace_id="a" * 32,
        span_id="r" * 16,
        parent_span_id=None,
        name="root",
        start_time=_utcnow(),
        tenant_id=tenant_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
    )
    trace = TraceArtifact(
        run_id=run_id,
        tenant_id=tenant_id,
        pipeline_id=pipeline_id,
        spans=[root],
    )
    # Unknown span ID → empty chain
    chain = trace.get_span_chain("0000000000000000")
    assert chain == []
