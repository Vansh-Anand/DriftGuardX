"""
DriftGuard-X v2 — Deterministic Mock Agentic RAG Pipeline

Each component has:
- A version ID
- A stable/experimental state
- A deterministic execution (same input + seed = same output)

This is the pipeline that generates real traces during Prompt 01.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from packages.contracts.src.models import (
    AgentPipeline,
    ComponentType,
    ComponentVersion,
    ComponentVersionState,
    RequestRun,
    RunStatus,
    SpanRecord,
    TraceArtifact,
)
from packages.evaluation.src.reliability import (
    aggregate_reliability_score,
    compute_reliability_vector,
)
from packages.policy.src.gate import evaluate_policy
from packages.replay.src.engine import (
    MockFinalResponseV1,
    MockGeneratorV1,
    MockMemoryReadV1,
    MockMemoryWriteV1,
    MockPolicyCheckV1,
    MockRerankerV1,
    MockRetrieverV1,
    MockRetrieverV2Experimental,
    MockToolCallV1,
)
from packages.trace_sdk.src.tracer import TraceContext, hash_payload

# ─── Registered Component Versions ────────────────────────────────────────────

def _make_config_hash(ct: str, tag: str) -> str:
    return hashlib.sha256(f"{ct}:{tag}".encode()).hexdigest()


# Stable versions
RETRIEVER_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0001-000000000001"),
    component_type=ComponentType.RETRIEVER,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("retriever", "v1"),
    description="Stable retriever — fresh, accurate document index",
)

# Experimental (known issue: stale evidence)
RETRIEVER_V2_EXP = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0001-000000000002"),
    component_type=ComponentType.RETRIEVER,
    version_tag="v2-exp",
    state=ComponentVersionState.EXPERIMENTAL,
    config_hash=_make_config_hash("retriever", "v2-exp"),
    description="Experimental retriever v2 — KNOWN ISSUE: stale index (triggers golden demo failure)",
)

RERANKER_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0002-000000000001"),
    component_type=ComponentType.RERANKER,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("reranker", "v1"),
    description="Stable reranker",
)

GENERATOR_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0003-000000000001"),
    component_type=ComponentType.GENERATOR,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("generator", "v1"),
    description="Stable generator",
)

MEMORY_READ_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0004-000000000001"),
    component_type=ComponentType.MEMORY_READ,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("memory_read", "v1"),
    description="Stable memory read",
)

MEMORY_WRITE_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0005-000000000001"),
    component_type=ComponentType.MEMORY_WRITE,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("memory_write", "v1"),
    description="Stable memory write (disabled in prototype)",
)

TOOL_CALL_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0006-000000000001"),
    component_type=ComponentType.TOOL_CALL,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("tool_call", "v1"),
    description="Stable tool call",
)

POLICY_CHECK_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0007-000000000001"),
    component_type=ComponentType.POLICY_CHECK,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("policy_check", "v1"),
    description="Stable policy check",
)

FINAL_RESPONSE_V1 = ComponentVersion(
    id=uuid.UUID("00000000-0000-0000-0008-000000000001"),
    component_type=ComponentType.FINAL_RESPONSE,
    version_tag="v1",
    state=ComponentVersionState.STABLE,
    config_hash=_make_config_hash("final_response", "v1"),
    description="Stable final response aggregator",
)

# All registered versions
ALL_COMPONENT_VERSIONS: list[ComponentVersion] = [
    RETRIEVER_V1,
    RETRIEVER_V2_EXP,
    RERANKER_V1,
    GENERATOR_V1,
    MEMORY_READ_V1,
    MEMORY_WRITE_V1,
    TOOL_CALL_V1,
    POLICY_CHECK_V1,
    FINAL_RESPONSE_V1,
]

COMPONENT_VERSION_BY_ID: dict[uuid.UUID, ComponentVersion] = {
    cv.id: cv for cv in ALL_COMPONENT_VERSIONS
}

# Pipeline definitions
PIPELINE_WITH_STABLE_RETRIEVER = AgentPipeline(
    id=uuid.UUID("00000000-0000-0000-AAAA-000000000001"),
    tenant_id=uuid.UUID("00000000-0000-0000-FFFF-000000000001"),
    name="Mock RAG Pipeline (Stable)",
    version="1.0.0",
    component_versions=[
        RETRIEVER_V1, RERANKER_V1, GENERATOR_V1,
        MEMORY_READ_V1, MEMORY_WRITE_V1, TOOL_CALL_V1,
        POLICY_CHECK_V1, FINAL_RESPONSE_V1,
    ],
)

PIPELINE_WITH_EXPERIMENTAL_RETRIEVER = AgentPipeline(
    id=uuid.UUID("00000000-0000-0000-AAAA-000000000002"),
    tenant_id=uuid.UUID("00000000-0000-0000-FFFF-000000000001"),
    name="Mock RAG Pipeline (Experimental Retriever)",
    version="1.1.0-exp",
    component_versions=[
        RETRIEVER_V2_EXP, RERANKER_V1, GENERATOR_V1,
        MEMORY_READ_V1, MEMORY_WRITE_V1, TOOL_CALL_V1,
        POLICY_CHECK_V1, FINAL_RESPONSE_V1,
    ],
)

DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-FFFF-000000000001")


# ─── Pipeline Executor ────────────────────────────────────────────────────────

_EXECUTOR_MAP = {
    (ComponentType.RETRIEVER, "v1"): MockRetrieverV1(),
    (ComponentType.RETRIEVER, "v2-exp"): MockRetrieverV2Experimental(),
    (ComponentType.RERANKER, "v1"): MockRerankerV1(),
    (ComponentType.GENERATOR, "v1"): MockGeneratorV1(),
    (ComponentType.MEMORY_READ, "v1"): MockMemoryReadV1(),
    (ComponentType.MEMORY_WRITE, "v1"): MockMemoryWriteV1(),
    (ComponentType.TOOL_CALL, "v1"): MockToolCallV1(),
    (ComponentType.POLICY_CHECK, "v1"): MockPolicyCheckV1(),
    (ComponentType.FINAL_RESPONSE, "v1"): MockFinalResponseV1(),
}

PIPELINE_EXECUTION_ORDER = [
    ComponentType.MEMORY_READ,
    ComponentType.RETRIEVER,
    ComponentType.RERANKER,
    ComponentType.GENERATOR,
    ComponentType.TOOL_CALL,
    ComponentType.POLICY_CHECK,
    ComponentType.MEMORY_WRITE,
    ComponentType.FINAL_RESPONSE,
]


class MockRAGPipeline:
    """Deterministic mock agentic RAG pipeline with full tracing."""

    def __init__(self, pipeline: AgentPipeline) -> None:
        self.pipeline = pipeline
        self._cv_map: dict[ComponentType, ComponentVersion] = {
            cv.component_type: cv for cv in pipeline.component_versions
        }

    def execute(
        self,
        *,
        run_id: uuid.UUID,
        query: str,
        seed: int = 42,
        is_synthetic: bool = True,
    ) -> tuple[RequestRun, TraceArtifact]:
        """
        Execute the pipeline deterministically.
        Returns (RequestRun, TraceArtifact) — caller must persist.
        """
        tenant_id = self.pipeline.tenant_id
        pipeline_id = self.pipeline.id

        # Check policy before running
        policy_check = evaluate_policy("create_run", "pipeline", {"pipeline_id": str(pipeline_id)})

        ctx = TraceContext(
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            run_id=run_id,
        )

        request_inputs: dict[str, Any] = {
            "query": query,
            "seed": seed,
            "tenant_id": str(tenant_id),
            "partition_id": f"{tenant_id}_{run_id}",
        }
        request_hash = hash_payload(request_inputs)

        started_at = datetime.now(UTC)
        all_spans: list[SpanRecord] = []

        # Root span
        root_builder = ctx.start_span("rag_pipeline", parent_span_id=None)
        root_span_id = root_builder.span_id

        current_inputs: dict[str, Any] = dict(request_inputs)
        faithfulness_score: float = 1.0
        has_error = False
        error_type: str | None = None
        error_message: str | None = None

        for component_type in PIPELINE_EXECUTION_ORDER:
            cv = self._cv_map.get(component_type)
            if cv is None:
                continue  # component not in this pipeline

            executor = _EXECUTOR_MAP.get((component_type, cv.version_tag))
            if executor is None:
                continue

            builder = ctx.start_span(
                f"{component_type.value}/{cv.version_tag}",
                parent_span_id=root_span_id,
            )
            builder.set_component(component_type, cv.id, cv.version_tag)
            builder.set_input(current_inputs)

            start = datetime.now(UTC)
            try:
                output = executor.execute(current_inputs, version=cv, seed=seed)
                builder._status_code = "OK"
            except Exception as e:
                output = {}
                has_error = True
                error_type = type(e).__name__
                error_message = str(e)
                builder.set_error(error_type, error_message)

            builder._end_time = datetime.now(UTC)
            builder._latency_ms = (builder._end_time - start).total_seconds() * 1000
            builder._start_time = start

            builder.set_output(output)

            if component_type == ComponentType.GENERATOR:
                builder.set_tokens(
                    output.get("token_count_input", 0),
                    output.get("token_count_output", 0),
                )
                faithfulness_score = float(output.get("faithfulness_score", 1.0))

            if component_type == ComponentType.POLICY_CHECK:
                builder.set_policy(output.get("policy_result", "allow"))

            span = builder.build()
            ctx.record_span(span)
            all_spans.append(span)

            current_inputs = {**current_inputs, **output}

        # Finish root span
        root_builder._end_time = datetime.now(UTC)
        root_builder._latency_ms = (
            (root_builder._end_time - root_builder._start_time).total_seconds() * 1000
        )
        root_builder._status_code = "ERROR" if has_error else "OK"
        root_span = root_builder.build()
        all_spans.insert(0, root_span)

        completed_at = datetime.now(UTC)
        total_latency = (completed_at - started_at).total_seconds() * 1000

        # Build trace
        trace = TraceArtifact(
            run_id=run_id,
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            spans=all_spans,
            root_span_id=root_span.span_id,
        )

        # Compute reliability
        reliability_vector = compute_reliability_vector(trace, faithfulness_score=faithfulness_score)
        reliability_score = aggregate_reliability_score(reliability_vector)

        # Compute totals
        total_tokens = sum(
            (s.token_count_input or 0) + (s.token_count_output or 0) for s in all_spans
        )
        response_hash = hash_payload(current_inputs.get("final_response", ""))

        # Build run
        run = RequestRun(
            id=run_id,
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            status=RunStatus.FAILED if has_error else RunStatus.COMPLETED,
            request_hash=request_hash,
            seed=seed,
            response_hash=response_hash,
            reliability_score=reliability_score,
            reliability_vector=reliability_vector,
            total_latency_ms=total_latency,
            total_tokens=total_tokens,
            total_cost_usd=0.0,  # mock: $0
            error_type=error_type,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
            is_synthetic=is_synthetic,
        )

        return run, trace
