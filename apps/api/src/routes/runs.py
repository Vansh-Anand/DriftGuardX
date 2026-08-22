"""
DriftGuard-X v2 — Run Routes

POST /v1/runs     — execute or accept a run
GET  /v1/runs     — list runs
GET  /v1/runs/{id} — get run with normalized trace
POST /v1/runs/{id}/replays — create deterministic replay
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.dependencies import get_current_tenant, PaginationParams, get_idempotency_key
from apps.api.src.database import get_db
from apps.api.src.models import (
    AgentPipelineORM,
    InterventionORM,
    ReplayEpisodeORM,
    ReplayStateManifestORM,
    RequestRunORM,
    SpanRecordORM,
    TenantORM,
    TraceArtifactORM,
)
from apps.api.src.pipeline.mock_rag import (
    DEMO_TENANT_ID,
    PIPELINE_WITH_EXPERIMENTAL_RETRIEVER,
    PIPELINE_WITH_STABLE_RETRIEVER,
    RETRIEVER_V1,
    RETRIEVER_V2_EXP,
    MockRAGPipeline,
)
from apps.api.src.schemas import (
    ReplayCreateRequest,
    ReplayResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
    SpanResponse,
    TraceResponse,
)
from packages.contracts.src.models import (
    ComponentType,
    Intervention,
    InterventionType,
)
from packages.policy.src.gate import evaluate_policy
from packages.replay.src.engine import ReplayEngine, VersionRegistry

router = APIRouter(prefix="/v1", tags=["runs"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_version_registry() -> VersionRegistry:
    from apps.api.src.pipeline.mock_rag import ALL_COMPONENT_VERSIONS
    registry = VersionRegistry()
    for cv in ALL_COMPONENT_VERSIONS:
        registry.register(cv)
    return registry


def _orm_to_run_response(run: RequestRunORM) -> RunResponse:
    return RunResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        pipeline_id=run.pipeline_id,
        status=run.status,
        request_hash=run.request_hash,
        reliability_score=run.reliability_score,
        reliability_vector=run.reliability_vector or {},
        total_latency_ms=run.total_latency_ms,
        total_tokens=run.total_tokens,
        total_cost_usd=run.total_cost_usd,
        error_type=run.error_type,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        is_synthetic=run.is_synthetic,
    )


# ─── POST /v1/runs ────────────────────────────────────────────────────────────

@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: RunCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> RunResponse:
    """Execute a deterministic mock RAG pipeline run and persist the trace."""

    # Policy check
    policy = evaluate_policy("create_run", "pipeline")
    if policy.action.value == "deny":
        raise HTTPException(status_code=403, detail=f"Policy denied: {policy.rationale}")

    # Select pipeline
    if request.use_experimental_retriever:
        pipeline = PIPELINE_WITH_EXPERIMENTAL_RETRIEVER
    else:
        pipeline = PIPELINE_WITH_STABLE_RETRIEVER

    run_id = uuid.uuid4()
    mock = MockRAGPipeline(pipeline)
    run_contract, trace_contract = mock.execute(
        run_id=run_id,
        query=request.query,
        seed=request.seed,
        is_synthetic=request.is_synthetic,
    )

    # Persist run
    run_orm = RequestRunORM(
        id=run_contract.id,
        tenant_id=run_contract.tenant_id,
        pipeline_id=run_contract.pipeline_id,
        status=run_contract.status.value if hasattr(run_contract.status, "value") else run_contract.status,
        request_hash=run_contract.request_hash,
        request_id=request.request_id,
        seed=run_contract.seed,
        response_hash=run_contract.response_hash,
        reliability_score=run_contract.reliability_score,
        reliability_vector=run_contract.reliability_vector,
        total_latency_ms=run_contract.total_latency_ms,
        total_tokens=run_contract.total_tokens,
        total_cost_usd=run_contract.total_cost_usd,
        error_type=run_contract.error_type,
        error_message=run_contract.error_message,
        started_at=run_contract.started_at,
        completed_at=run_contract.completed_at,
        is_synthetic=run_contract.is_synthetic,
    )
    db.add(run_orm)

    # Persist spans
    for span in trace_contract.spans:
        span_orm = SpanRecordORM(
            id=uuid.uuid4(),
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            run_id=run_id,
            tenant_id=span.tenant_id,
            pipeline_id=span.pipeline_id,
            name=span.name,
            kind=str(span.kind.value) if hasattr(span.kind, "value") else str(span.kind),
            start_time=span.start_time,
            end_time=span.end_time,
            status_code=span.status_code,
            status_message=span.status_message,
            attributes_json=span.attributes,
            component_type=str(span.component_type.value) if span.component_type and hasattr(span.component_type, "value") else span.component_type,
            component_version_id=span.component_version_id,
            component_version_tag=span.component_version_tag,
            input_hash=span.input_hash,
            output_hash=span.output_hash,
            latency_ms=span.latency_ms,
            token_count_input=span.token_count_input,
            token_count_output=span.token_count_output,
            cost_usd=span.cost_usd,
            policy_result=span.policy_result,
            policy_rule_id=span.policy_rule_id,
            error_type=span.error_type,
            error_message=span.error_message,
        )
        db.add(span_orm)

    # Persist trace artifact (spans as JSONB)
    spans_json = [
        {
            "trace_id": s.trace_id,
            "span_id": s.span_id,
            "parent_span_id": s.parent_span_id,
            "name": s.name,
            "kind": str(s.kind.value) if hasattr(s.kind, "value") else str(s.kind),
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "status_code": s.status_code,
            "component_type": str(s.component_type.value) if s.component_type and hasattr(s.component_type, "value") else s.component_type,
            "component_version_tag": s.component_version_tag,
            "input_hash": s.input_hash,
            "output_hash": s.output_hash,
            "latency_ms": s.latency_ms,
            "token_count_input": s.token_count_input,
            "token_count_output": s.token_count_output,
            "policy_result": s.policy_result,
            "error_type": s.error_type,
        }
        for s in trace_contract.spans
    ]

    trace_orm = TraceArtifactORM(
        id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=run_contract.tenant_id,
        pipeline_id=run_contract.pipeline_id,
        spans_json=spans_json,
        root_span_id=trace_contract.root_span_id,
        total_span_count=len(trace_contract.spans),
    )
    db.add(trace_orm)

    await db.flush()
    return _orm_to_run_response(run_orm)


# ─── GET /v1/runs ─────────────────────────────────────────────────────────────

@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    pagination: PaginationParams = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> RunListResponse:
    """List all runs with pagination, filtered by tenant."""
    query = select(RequestRunORM).where(RequestRunORM.tenant_id == tenant.id).order_by(RequestRunORM.created_at.desc())
    count_query = select(func.count()).select_from(RequestRunORM).where(RequestRunORM.tenant_id == tenant.id)

    if status_filter:
        query = query.where(RequestRunORM.status == status_filter)
        count_query = count_query.where(RequestRunORM.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset(pagination.skip).limit(pagination.limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return RunListResponse(
        runs=[_orm_to_run_response(r) for r in runs],
        total=total,
        page=(pagination.skip // pagination.limit) + 1,
        page_size=pagination.limit,
    )


# ─── GET /v1/runs/{id} ────────────────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> RunResponse:
    """Get a run by ID."""
    result = await db.execute(select(RequestRunORM).where(RequestRunORM.id == run_id, RequestRunORM.tenant_id == tenant.id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _orm_to_run_response(run)


# ─── GET /v1/runs/{id}/trace ──────────────────────────────────────────────────

@router.get("/runs/{run_id}/trace", response_model=TraceResponse)
async def get_run_trace(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> TraceResponse:
    """Get the normalized trace for a run."""
    result = await db.execute(
        select(TraceArtifactORM).where(TraceArtifactORM.run_id == run_id, TraceArtifactORM.tenant_id == tenant.id)
    )
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace for run {run_id} not found")

    spans_data: list[dict] = trace.spans_json if isinstance(trace.spans_json, list) else []
    span_responses = [
        SpanResponse(
            trace_id=s.get("trace_id", ""),
            span_id=s.get("span_id", ""),
            parent_span_id=s.get("parent_span_id"),
            name=s.get("name", ""),
            kind=s.get("kind", "INTERNAL"),
            start_time=datetime.fromisoformat(s["start_time"]) if s.get("start_time") else datetime.now(timezone.utc),
            end_time=datetime.fromisoformat(s["end_time"]) if s.get("end_time") else None,
            status_code=s.get("status_code", "UNSET"),
            component_type=s.get("component_type"),
            component_version_tag=s.get("component_version_tag"),
            input_hash=s.get("input_hash"),
            output_hash=s.get("output_hash"),
            latency_ms=s.get("latency_ms"),
            token_count_input=s.get("token_count_input"),
            token_count_output=s.get("token_count_output"),
            policy_result=s.get("policy_result"),
            error_type=s.get("error_type"),
            error_message=s.get("error_message"),
        )
        for s in spans_data
    ]

    # Get trace_id from first span
    trace_id = spans_data[0]["trace_id"] if spans_data else ""

    return TraceResponse(
        run_id=run_id,
        trace_id=trace_id,
        total_span_count=trace.total_span_count,
        root_span_id=trace.root_span_id,
        spans=span_responses,
    )


# ─── POST /v1/runs/{id}/replays ───────────────────────────────────────────────

@router.post(
    "/runs/{run_id}/replays",
    response_model=ReplayResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_replay(
    run_id: uuid.UUID,
    request: ReplayCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> ReplayResponse:
    """
    Create a deterministic replay for a run.
    Swaps the retriever version (v2-exp → v1) while pinning all other versions.
    Requires human approval in production (demo mode: auto-approved for synthetic runs).
    """
    # Policy check
    policy = evaluate_policy("create_replay", f"run:{run_id}")
    if policy.action.value == "deny":
        raise HTTPException(status_code=403, detail=f"Policy denied: {policy.rationale}")

    # Load original run
    run_result = await db.execute(select(RequestRunORM).where(RequestRunORM.id == run_id, RequestRunORM.tenant_id == tenant.id))
    original_run_orm = run_result.scalar_one_or_none()
    if original_run_orm is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if not original_run_orm.is_synthetic:
        raise HTTPException(
            status_code=400,
            detail="Replay only supported for synthetic/demo runs in Prompt 01. Non-synthetic runs require human approval.",
        )

    # Load original trace
    trace_result = await db.execute(
        select(TraceArtifactORM).where(TraceArtifactORM.run_id == run_id)
    )
    original_trace_orm = trace_result.scalar_one_or_none()
    if original_trace_orm is None:
        raise HTTPException(status_code=404, detail=f"Trace for run {run_id} not found")

    # Rebuild trace contract from stored JSON
    from packages.contracts.src.models import SpanRecord, TraceArtifact, SpanKind

    spans_data: list[dict] = original_trace_orm.spans_json if isinstance(original_trace_orm.spans_json, list) else []
    span_contracts = []
    for s in spans_data:
        try:
            ct = None
            if s.get("component_type"):
                ct = ComponentType(s["component_type"])
            span_contracts.append(
                SpanRecord(
                    trace_id=s.get("trace_id", "0" * 32),
                    span_id=s.get("span_id", "0" * 16),
                    parent_span_id=s.get("parent_span_id"),
                    name=s.get("name", ""),
                    kind=SpanKind(s.get("kind", "INTERNAL")),
                    start_time=datetime.fromisoformat(s["start_time"]),
                    end_time=datetime.fromisoformat(s["end_time"]) if s.get("end_time") else None,
                    status_code=s.get("status_code", "OK"),
                    tenant_id=original_trace_orm.tenant_id,
                    pipeline_id=original_trace_orm.pipeline_id,
                    run_id=run_id,
                    component_type=ct,
                    component_version_tag=s.get("component_version_tag"),
                    input_hash=s.get("input_hash"),
                    output_hash=s.get("output_hash"),
                    latency_ms=s.get("latency_ms"),
                    token_count_input=s.get("token_count_input"),
                    token_count_output=s.get("token_count_output"),
                    policy_result=s.get("policy_result"),
                    error_type=s.get("error_type"),
                )
            )
        except Exception:
            pass  # skip malformed spans

    original_trace = TraceArtifact(
        run_id=run_id,
        tenant_id=original_trace_orm.tenant_id,
        pipeline_id=original_trace_orm.pipeline_id,
        spans=span_contracts,
        root_span_id=original_trace_orm.root_span_id,
    )

    from packages.contracts.src.models import RunStatus

    original_run_contract = __import__("packages.contracts.src.models", fromlist=["RequestRun"]).RequestRun(
        id=original_run_orm.id,
        tenant_id=original_run_orm.tenant_id,
        pipeline_id=original_run_orm.pipeline_id,
        status=RunStatus(original_run_orm.status),
        request_hash=original_run_orm.request_hash,
        seed=original_run_orm.seed,
        response_hash=original_run_orm.response_hash,
        reliability_score=original_run_orm.reliability_score,
        reliability_vector=original_run_orm.reliability_vector or {},
        total_latency_ms=original_run_orm.total_latency_ms,
        total_tokens=original_run_orm.total_tokens,
        is_synthetic=original_run_orm.is_synthetic,
    )

    # Determine swap: only retriever rollback supported in Prompt 01
    from_version = RETRIEVER_V2_EXP
    to_version = RETRIEVER_V1

    # Create intervention record
    intervention = Intervention(
        run_id=run_id,
        tenant_id=original_run_orm.tenant_id,
        intervention_type=InterventionType.ROLLBACK,
        target_component_type=ComponentType.RETRIEVER,
        from_version_id=from_version.id,
        to_version_id=to_version.id,
        from_version_tag=from_version.version_tag,
        to_version_tag=to_version.version_tag,
        rationale="Experimental retriever v2 returns stale evidence. Rolling back to stable v1.",
        approved_by="demo-system",  # auto-approved for synthetic demo
        requires_human_approval=True,  # marked as required (not auto-applied to production)
    )

    intervention_orm = InterventionORM(
        id=intervention.id,
        run_id=run_id,
        tenant_id=intervention.tenant_id,
        intervention_type=intervention.intervention_type.value if hasattr(intervention.intervention_type, "value") else intervention.intervention_type,
        target_component_type=intervention.target_component_type.value if hasattr(intervention.target_component_type, "value") else intervention.target_component_type,
        from_version_id=intervention.from_version_id,
        to_version_id=intervention.to_version_id,
        from_version_tag=intervention.from_version_tag,
        to_version_tag=intervention.to_version_tag,
        rationale=intervention.rationale,
        approved_by=intervention.approved_by,
        requires_human_approval=intervention.requires_human_approval,
    )
    db.add(intervention_orm)

    # Execute replay
    registry = _build_version_registry()
    engine = ReplayEngine(registry)

    original_rv = original_run_orm.reliability_vector or {}
    request_inputs = {"query": "What are the latest AI safety guidelines?", "seed": request.seed}

    # Create ReplayStateManifest
    from packages.contracts.src.models import ReplayStateManifest
    manifest_contract = ReplayStateManifest(
        run_id=run_id,
        tenant_id=original_run_orm.tenant_id,
        model_provider="mock-provider",
        model_identifier="mock-model",
        model_config_hash="mock-config-hash",
        prompt_template_hash="mock-prompt-hash",
        retriever_version=to_version.version_tag,
        embedding_model_version="mock-embed",
        vector_index_snapshot_id="mock-index",
        tool_schemas_hash="mock-schema-hash",
        policy_config_hash="mock-policy-hash",
        memory_snapshot_id="mock-memory",
        random_seed=request.seed,
        container_image_digest="mock-container",
        dependency_lockfile_hash="mock-lockfile",
        trace_root_hash="mock-trace-hash",
    )

    manifest_orm = ReplayStateManifestORM(
        id=manifest_contract.id,
        run_id=manifest_contract.run_id,
        tenant_id=manifest_contract.tenant_id,
        model_provider=manifest_contract.model_provider,
        model_identifier=manifest_contract.model_identifier,
        model_config_hash=manifest_contract.model_config_hash,
        prompt_template_hash=manifest_contract.prompt_template_hash,
        retriever_version=manifest_contract.retriever_version,
        embedding_model_version=manifest_contract.embedding_model_version,
        vector_index_snapshot_id=manifest_contract.vector_index_snapshot_id,
        tool_schemas_hash=manifest_contract.tool_schemas_hash,
        policy_config_hash=manifest_contract.policy_config_hash,
        memory_snapshot_id=manifest_contract.memory_snapshot_id,
        random_seed=manifest_contract.random_seed,
        generation_parameters=manifest_contract.generation_parameters,
        container_image_digest=manifest_contract.container_image_digest,
        dependency_lockfile_hash=manifest_contract.dependency_lockfile_hash,
        trace_root_hash=manifest_contract.trace_root_hash,
        manifest_hash=manifest_contract.manifest_hash,
    )
    db.add(manifest_orm)

    episode, replay_trace = engine.execute_replay(
        original_run=original_run_contract,
        original_trace=original_trace,
        intervention=intervention,
        replay_version=to_version,
        original_reliability_vector=original_rv,
        request_inputs=request_inputs,
        seed=request.seed,
        manifest=manifest_contract,
    )

    # Persist replay episode
    episode_orm = ReplayEpisodeORM(
        id=episode.replay_id,
        original_run_id=run_id,
        tenant_id=episode.tenant_id,
        pipeline_id=original_run_orm.pipeline_id,
        intervention_id=intervention.id,
        status=episode.status.value if hasattr(episode.status, "value") else episode.status,
        swapped_component_type=episode.swapped_component_type.value if hasattr(episode.swapped_component_type, "value") else episode.swapped_component_type,
        original_version_id=episode.original_version_id,
        replay_version_id=episode.replay_version_id,
        original_version_tag=episode.original_version_tag,
        replay_version_tag=episode.replay_version_tag,
        pinned_version_ids=episode.pinned_version_ids,
        original_reliability_vector=episode.original_reliability_vector,
        replay_reliability_vector=episode.replay_reliability_vector,
        reliability_delta=episode.reliability_delta,
        original_reliability_score=episode.original_reliability_score,
        replay_reliability_score=episode.replay_reliability_score,
        reliability_improvement=episode.reliability_improvement,
        original_request_hash=episode.original_request_hash,
        replay_response_hash=episode.replay_response_hash,
        seed=episode.seed,
        completed_at=episode.completed_at,
        is_synthetic=episode.is_synthetic,
        manifest_id=episode.manifest_id,
        is_pinned=episode.is_pinned,
    )
    db.add(episode_orm)

    # Persist replay trace as a TraceArtifact
    replay_spans_json = [
        {
            "trace_id": s.trace_id,
            "span_id": s.span_id,
            "parent_span_id": s.parent_span_id,
            "name": s.name,
            "kind": str(s.kind.value) if hasattr(s.kind, "value") else str(s.kind),
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "status_code": s.status_code,
            "component_type": str(s.component_type.value) if s.component_type and hasattr(s.component_type, "value") else s.component_type,
            "component_version_tag": s.component_version_tag,
            "latency_ms": s.latency_ms,
            "policy_result": s.policy_result,
            "error_type": s.error_type,
        }
        for s in replay_trace.spans
    ]
    replay_trace_orm = TraceArtifactORM(
        id=uuid.uuid4(),
        run_id=episode.replay_id,
        tenant_id=episode.tenant_id,
        pipeline_id=original_run_orm.pipeline_id,
        spans_json=replay_spans_json,
        root_span_id=replay_trace.root_span_id,
        total_span_count=len(replay_trace.spans),
    )
    db.add(replay_trace_orm)
    await db.flush()

    return ReplayResponse(
        id=episode_orm.id,
        original_run_id=episode_orm.original_run_id,
        status=episode_orm.status,
        swapped_component_type=episode_orm.swapped_component_type,
        original_version_tag=episode_orm.original_version_tag,
        replay_version_tag=episode_orm.replay_version_tag,
        original_reliability_score=episode_orm.original_reliability_score,
        replay_reliability_score=episode_orm.replay_reliability_score,
        reliability_improvement=episode_orm.reliability_improvement,
        original_reliability_vector=episode_orm.original_reliability_vector,
        replay_reliability_vector=episode_orm.replay_reliability_vector,
        reliability_delta=episode_orm.reliability_delta,
        created_at=episode_orm.created_at,
        completed_at=episode_orm.completed_at,
        is_synthetic=episode_orm.is_synthetic,
        manifest_id=manifest_orm.id,
        manifest_hash=manifest_orm.manifest_hash,
        is_pinned=episode_orm.is_pinned,
    )
