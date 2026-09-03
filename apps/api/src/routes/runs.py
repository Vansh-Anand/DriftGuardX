"""
DriftGuard-X v2 — Run Routes

POST /v1/runs     — execute or accept a run
GET  /v1/runs     — list runs
GET  /v1/runs/{id} — get run with normalized trace
POST /v1/runs/{id}/replays — create deterministic replay
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from apps.api.src.database import get_db
from apps.api.src.dependencies import PaginationParams, get_current_tenant, get_idempotency_key
from apps.api.src.models import (
    IdempotencyKeyORM,
    InterventionORM,
    ReplayEpisodeORM,
    ReplayStateManifestORM,
    RequestRunORM,
    SpanRecordORM,
    TraceArtifactORM,
)
from apps.api.src.pipeline.mock_rag import (
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
    ComponentVersion,
    Intervention,
    InterventionType,
    ReplayStateManifest,
)
from packages.policy.src.gate import PolicyGate, evaluate_policy
from packages.replay.src.engine import (
    MOCK_RAG_CORPUS_VERSION_ID,
    MOCK_RAG_EMBEDDING_MODEL_VERSION,
    MOCK_RETRIEVER_V1_DOCUMENT_IDS,
    ReplayEngine,
    VersionRegistry,
)
from packages.trace_sdk.src.tracer import hash_payload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from packages.contracts.src.auth import Tenant

router = APIRouter(prefix="/v1", tags=["runs"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_version_registry() -> VersionRegistry:
    from apps.api.src.pipeline.mock_rag import ALL_COMPONENT_VERSIONS

    registry = VersionRegistry()
    for cv in ALL_COMPONENT_VERSIONS:
        registry.register(cv)
    return registry


_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _file_sha256(relative_path: str) -> str:
    """Hash a required runtime artifact, failing closed when it is absent."""
    path = _REPOSITORY_ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"Required replay provenance artifact is missing: {relative_path}")
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_replay_manifest(
    *,
    original_run: RequestRunORM,
    original_trace: TraceArtifactORM,
    seed: int,
    original_query: str,
) -> ReplayStateManifest:
    """Bind a replay to actual code, lock, trace, policy, and component state."""
    lock_digest = _file_sha256("uv.lock")
    replay_engine_digest = _file_sha256("packages/replay/src/engine.py")
    api_route_digest = _file_sha256("apps/api/src/routes/runs.py")

    generation_parameters: dict[str, object] = {
        "sampling": "deterministic",
        "temperature": 0.0,
        "seed": seed,
    }
    component_manifest = [
        {
            "component_type": str(component.component_type),
            "version_id": str(component.id),
            "version_tag": component.version_tag,
            "config_hash": component.config_hash,
        }
        for component in PIPELINE_WITH_STABLE_RETRIEVER.component_versions
    ]
    # Get the original retriever version from the pipeline
    retriever_cv = PIPELINE_WITH_STABLE_RETRIEVER.component_versions[0] # Usually retriever is first or we can get it from the trace
    for cv in PIPELINE_WITH_STABLE_RETRIEVER.component_versions:
        if cv.component_type == ComponentType.RETRIEVER:
            retriever_cv = cv
            break

    retriever_settings: dict[str, object] = {
        "top_k": len(MOCK_RETRIEVER_V1_DOCUMENT_IDS),
        "ordering": "score_desc",
        "version_id": str(retriever_cv.id),
        "config_hash": retriever_cv.config_hash,
    }
    policy_definition = {
        "always_allow": sorted(PolicyGate.ALWAYS_ALLOW_ACTIONS),
        "needs_approval": sorted(PolicyGate.NEEDS_APPROVAL_ACTIONS),
        "always_deny": sorted(PolicyGate.ALWAYS_DENY_ACTIONS),
        "default": "deny",
    }
    local_artifact_digest = hash_payload(
        {
            "api_route_sha256": api_route_digest,
            "replay_engine_sha256": replay_engine_digest,
            "dependency_lock_sha256": lock_digest,
        }
    )
    execution_digest = os.environ.get("DGX_CONTAINER_IMAGE_DIGEST")
    if not execution_digest:
        execution_digest = f"local-process:sha256:{local_artifact_digest}"

    corpus_snapshot = {
        "corpus_version": MOCK_RAG_CORPUS_VERSION_ID,
        "document_ids": list(MOCK_RETRIEVER_V1_DOCUMENT_IDS),
        "retriever_settings": retriever_settings,
    }
    trace_root_hash = hash_payload(
        {
            "root_span_id": original_trace.root_span_id,
            "total_span_count": original_trace.total_span_count,
            "spans": original_trace.spans_json,
        }
    )
    # Construct multi_agent_topology from trace spans dynamically
    multi_agent_topology = []
    if original_trace and original_trace.spans_json:
        # spans_json is a dict of span_id -> span_dict or a list
        spans = original_trace.spans_json
        if isinstance(spans, dict):
            spans = list(spans.values())
            
        agent_spans = [s for s in spans if s.get("component_type") == ComponentType.AGENT.value or s.get("component_type") == "AGENT"]
        
        # Build node relationships
        nodes = {}
        for s in agent_spans:
            agent_type = s.get("attributes", {}).get("dgx.agent.type", s.get("name"))
            span_id = s.get("span_id")
            source_span_id = s.get("attributes", {}).get("dgx.causal.source_span_id")
            nodes[span_id] = {"agent": agent_type, "span_id": span_id, "next": [], "source": source_span_id}
            
        # Link next based on source
        for span_id, data in nodes.items():
            if data["source"] and data["source"] in nodes:
                nodes[data["source"]]["next"].append(data["agent"])
                
        for node in nodes.values():
            multi_agent_topology.append({"agent": node["agent"], "next": list(set(node["next"]))})
            
    if not multi_agent_topology:
        multi_agent_topology = [{"agent": "orchestrator", "next": []}]

    return ReplayStateManifest(
        run_id=original_run.id,
        tenant_id=original_run.tenant_id,
        # Raw prompts are deliberately not retained. This is the canonical hash
        # of the original request envelope containing the query and seed.
        original_query=original_query,
        original_query_hash=original_run.request_hash,
        corpus_version_id=MOCK_RAG_CORPUS_VERSION_ID,
        model_provider="local-deterministic",
        model_identifier="MockGeneratorV1@v1",
        model_config_hash=hash_payload(
            {
                "components": component_manifest,
                "generation": generation_parameters,
                "topology": multi_agent_topology,
            }
        ),
        prompt_template_hash=hash_payload(
            {
                "callable": "packages.replay.src.engine.MockGeneratorV1.execute",
                "source_module_sha256": replay_engine_digest,
            }
        ),
        retriever_version=retriever_cv.version_tag,
        retriever_settings=retriever_settings,
        retrieved_chunk_ids=list(MOCK_RETRIEVER_V1_DOCUMENT_IDS),
        embedding_model_version=MOCK_RAG_EMBEDDING_MODEL_VERSION,
        vector_index_snapshot_id=f"mock-rag-index@sha256:{hash_payload(corpus_snapshot)}",
        tool_schemas_hash=hash_payload({"tools": []}),
        policy_config_hash=hash_payload(policy_definition),
        memory_snapshot_id=f"stateless@sha256:{hash_payload({'persistent_memory': False})}",
        random_seed=seed,
        generation_parameters=generation_parameters,
        container_image_digest=execution_digest,
        dependency_lockfile_hash=lock_digest,
        trace_root_hash=trace_root_hash,
    )


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
    tenant: Tenant = Depends(get_current_tenant),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> RunResponse:
    """Execute a deterministic mock RAG pipeline run and persist the trace."""

    if not request.is_synthetic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non-synthetic execution is unavailable on the deterministic mock pipeline",
        )

    effective_idempotency_key = idempotency_key or request.request_id
    if idempotency_key and request.request_id and idempotency_key != request.request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header and body idempotency keys do not match",
        )
    if effective_idempotency_key:
        existing_key = await db.scalar(
            select(IdempotencyKeyORM).where(
                IdempotencyKeyORM.tenant_id == tenant.id,
                IdempotencyKeyORM.key == effective_idempotency_key,
            )
        )
        if existing_key is not None:
            if existing_key.request_path != "/v1/runs":
                raise HTTPException(status_code=409, detail="Idempotency key is already in use")
            return RunResponse.model_validate(existing_key.response_body)

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
        tenant_id=tenant.id,
        pipeline_id=run_contract.pipeline_id,
        status=(
            run_contract.status.value
            if hasattr(run_contract.status, "value")
            else run_contract.status
        ),
        request_hash=run_contract.request_hash,
        request_id=effective_idempotency_key,
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
            tenant_id=tenant.id,
            pipeline_id=span.pipeline_id,
            name=span.name,
            kind=str(span.kind.value) if hasattr(span.kind, "value") else str(span.kind),
            start_time=span.start_time,
            end_time=span.end_time,
            status_code=span.status_code,
            status_message=span.status_message,
            attributes_json=span.attributes,
            component_type=(
                str(span.component_type.value)
                if span.component_type and hasattr(span.component_type, "value")
                else span.component_type
            ),
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
            "component_type": (
                str(s.component_type.value)
                if s.component_type and hasattr(s.component_type, "value")
                else s.component_type
            ),
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
        tenant_id=tenant.id,
        pipeline_id=run_contract.pipeline_id,
        spans_json=spans_json,
        root_span_id=trace_contract.root_span_id,
        total_span_count=len(trace_contract.spans),
    )
    db.add(trace_orm)

    manifest_contract = _build_replay_manifest(
        original_run=run_orm,
        original_trace=trace_orm,
        seed=request.seed,
        original_query=request.query,
    )

    manifest_orm = ReplayStateManifestORM(
        id=manifest_contract.id,
        run_id=manifest_contract.run_id,
        tenant_id=manifest_contract.tenant_id,
        original_query=manifest_contract.original_query,
        original_query_hash=manifest_contract.original_query_hash,
        corpus_version_id=manifest_contract.corpus_version_id,
        model_provider=manifest_contract.model_provider,
        model_identifier=manifest_contract.model_identifier,
        model_config_hash=manifest_contract.model_config_hash,
        prompt_template_hash=manifest_contract.prompt_template_hash,
        retriever_version=manifest_contract.retriever_version,
        retriever_settings=manifest_contract.retriever_settings,
        retrieved_chunk_ids=manifest_contract.retrieved_chunk_ids,
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

    await db.flush()
    response = _orm_to_run_response(run_orm)
    if effective_idempotency_key:
        db.add(
            IdempotencyKeyORM(
                tenant_id=tenant.id,
                key=effective_idempotency_key,
                request_path="/v1/runs",
                response_status=status.HTTP_201_CREATED,
                response_body=response.model_dump(mode="json"),
            )
        )
        await db.flush()
    return response


# ─── POST /v1/runs/register ───────────────────────────────────────────────────


from apps.api.src.schemas import RunRegisterRequest, RunRegisterResponse


@router.post(
    "/runs/register", response_model=RunRegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register_run(
    request: RunRegisterRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> RunRegisterResponse:
    """Register an external or custom run in preparation for span ingestion."""
    run_id = request.run_id or uuid.uuid4()

    run_orm = RequestRunORM(
        id=run_id,
        tenant_id=tenant.id,
        pipeline_id=request.pipeline_id,
        status="running",
        request_hash=hash_payload(request.query),
        request_id=None,
        seed=42,  # default
        response_hash=None,
        reliability_score=None,
        reliability_vector={},
        total_latency_ms=0.0,
        total_tokens=0,
        total_cost_usd=0.0,
        error_type=None,
        error_message=None,
        started_at=datetime.now(UTC),
        completed_at=None,
        is_synthetic=request.is_synthetic,
    )
    db.add(run_orm)

    # We must also create a placeholder trace artifact to be filled later or by ingestion
    trace_orm = TraceArtifactORM(
        id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=tenant.id,
        pipeline_id=request.pipeline_id,
        spans_json=[],
        root_span_id=None,
        total_span_count=0,
    )
    db.add(trace_orm)

    await db.flush()

    return RunRegisterResponse(
        id=run_orm.id,
        tenant_id=run_orm.tenant_id,
        pipeline_id=run_orm.pipeline_id,
        status=run_orm.status,
        is_synthetic=run_orm.is_synthetic,
    )


# ─── GET /v1/runs ─────────────────────────────────────────────────────────────


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    pagination: PaginationParams = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> RunListResponse:
    """List all runs with pagination, filtered by tenant."""
    query = (
        select(RequestRunORM)
        .where(RequestRunORM.tenant_id == tenant.id)
        .order_by(RequestRunORM.created_at.desc())
    )
    count_query = (
        select(func.count()).select_from(RequestRunORM).where(RequestRunORM.tenant_id == tenant.id)
    )

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
    tenant: Tenant = Depends(get_current_tenant),
) -> RunResponse:
    """Get a run by ID."""
    result = await db.execute(
        select(RequestRunORM).where(
            RequestRunORM.id == run_id, RequestRunORM.tenant_id == tenant.id
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _orm_to_run_response(run)


# ─── GET /v1/runs/{id}/trace ──────────────────────────────────────────────────


@router.get("/runs/{run_id}/trace", response_model=TraceResponse)
async def get_run_trace(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> TraceResponse:
    """Get the normalized trace for a run."""
    result = await db.execute(
        select(TraceArtifactORM).where(
            TraceArtifactORM.run_id == run_id, TraceArtifactORM.tenant_id == tenant.id
        )
    )
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace for run {run_id} not found")

    spans_data: list[dict[str, Any]] = (
        trace.spans_json if isinstance(trace.spans_json, list) else []
    )
    span_responses = [
        SpanResponse(
            trace_id=s.get("trace_id", ""),
            span_id=s.get("span_id", ""),
            parent_span_id=s.get("parent_span_id"),
            name=s.get("name", ""),
            kind=s.get("kind", "INTERNAL"),
            start_time=(
                datetime.fromisoformat(s["start_time"])
                if s.get("start_time")
                else datetime.now(UTC)
            ),
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
    tenant: Tenant = Depends(get_current_tenant),
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
    run_result = await db.execute(
        select(RequestRunORM).where(
            RequestRunORM.id == run_id, RequestRunORM.tenant_id == tenant.id
        )
    )
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
        select(TraceArtifactORM).where(
            TraceArtifactORM.run_id == run_id,
            TraceArtifactORM.tenant_id == tenant.id,
        )
    )
    original_trace_orm = trace_result.scalar_one_or_none()
    if original_trace_orm is None:
        raise HTTPException(status_code=404, detail=f"Trace for run {run_id} not found")

    # Rebuild trace contract from stored JSON
    from packages.contracts.src.models import SpanKind, SpanRecord, TraceArtifact

    spans_data: list[dict[str, Any]] = (
        original_trace_orm.spans_json if isinstance(original_trace_orm.spans_json, list) else []
    )
    span_contracts: list[SpanRecord] = []
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
        except (ValueError, RuntimeError, KeyError, TypeError, OSError):
            pass  # skip malformed spans

    original_trace = TraceArtifact(
        run_id=run_id,
        tenant_id=original_trace_orm.tenant_id,
        pipeline_id=original_trace_orm.pipeline_id,
        spans=span_contracts,
        root_span_id=original_trace_orm.root_span_id,
    )

    from packages.contracts.src.models import RunStatus

    original_run_contract = __import__(
        "packages.contracts.src.models", fromlist=["RequestRun"]
    ).RequestRun(
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

    # Determine swap dynamically
    intervention_spec = request.intervention
    target_component = intervention_spec.target_component
    intervention_type = intervention_spec.intervention_type

    registry = _build_version_registry()
    
    # Try fetching by tag if candidate_version looks like a tag, otherwise assume it might be a UUID.
    # In Prompt 01, mock registry uses version_tags
    to_version = None
    if intervention_spec.candidate_version:
        to_version = registry.get_by_type_and_tag(target_component, intervention_spec.candidate_version)
        if not to_version:
            try:
                cv_id = uuid.UUID(intervention_spec.candidate_version)
                to_version = registry.get(cv_id)
            except ValueError:
                pass
    
    if not to_version:
        raise HTTPException(status_code=400, detail=f"Target component version not found: {intervention_spec.candidate_version}")

    from_version = None
    if intervention_spec.current_version:
        from_version = registry.get_by_type_and_tag(target_component, intervention_spec.current_version)
        if not from_version:
            try:
                cv_id = uuid.UUID(intervention_spec.current_version)
                from_version = registry.get(cv_id)
            except ValueError:
                pass

    if not from_version:
        raise HTTPException(status_code=400, detail=f"Source component version not found: {intervention_spec.current_version}")

    # Create intervention record
    intervention_orm = InterventionORM(
        id=uuid.UUID(intervention_spec.spec_id),
        run_id=run_id,
        tenant_id=original_run_orm.tenant_id,
        intervention_type=str(intervention_type.value) if hasattr(intervention_type, "value") else str(intervention_type),
        target_component_type=str(target_component.value) if hasattr(target_component, "value") else str(target_component),
        from_version_id=from_version.id,
        to_version_id=to_version.id,
        from_version_tag=from_version.version_tag,
        to_version_tag=to_version.version_tag,
        rationale=intervention_spec.rollback_plan or "",
        approved_by="demo-system",  # auto-approved for synthetic demo
        requires_human_approval=True,  # marked as required (not auto-applied to production)
    )
    db.add(intervention_orm)

    # Fetch manifest from DB
    manifest_result = await db.execute(
        select(ReplayStateManifestORM).where(
            ReplayStateManifestORM.run_id == run_id,
            ReplayStateManifestORM.tenant_id == tenant.id,
        )
    )
    manifest_orm = manifest_result.scalar_one_or_none()
    if not manifest_orm:
        raise HTTPException(status_code=404, detail=f"Manifest for run {run_id} not found")

    manifest_contract = ReplayStateManifest(
        id=manifest_orm.id,
        run_id=manifest_orm.run_id,
        tenant_id=manifest_orm.tenant_id,
        original_query=manifest_orm.original_query,
        original_query_hash=manifest_orm.original_query_hash,
        corpus_version_id=manifest_orm.corpus_version_id,
        model_provider=manifest_orm.model_provider,
        model_identifier=manifest_orm.model_identifier,
        model_config_hash=manifest_orm.model_config_hash,
        prompt_template_hash=manifest_orm.prompt_template_hash,
        retriever_version=manifest_orm.retriever_version,
        retriever_settings=manifest_orm.retriever_settings,
        retrieved_chunk_ids=manifest_orm.retrieved_chunk_ids,
        embedding_model_version=manifest_orm.embedding_model_version,
        vector_index_snapshot_id=manifest_orm.vector_index_snapshot_id,
        tool_schemas_hash=manifest_orm.tool_schemas_hash,
        policy_config_hash=manifest_orm.policy_config_hash,
        memory_snapshot_id=manifest_orm.memory_snapshot_id,
        random_seed=manifest_orm.random_seed,
        generation_parameters=manifest_orm.generation_parameters,
        container_image_digest=manifest_orm.container_image_digest,
        dependency_lockfile_hash=manifest_orm.dependency_lockfile_hash,
        trace_root_hash=manifest_orm.trace_root_hash,
        manifest_hash=manifest_orm.manifest_hash,
    )

    # Execute replay
    engine = ReplayEngine(registry)

    original_rv = original_run_orm.reliability_vector or {}

    episode, replay_trace = engine.execute_replay(
        original_run=original_run_contract,
        original_trace=original_trace,
        intervention=intervention_spec,
        replay_version=to_version,
        original_reliability_vector=original_rv,
        seed=request.seed,
        manifest=manifest_contract,
    )

    # Persist replay episode
    episode_orm = ReplayEpisodeORM(
        id=episode.replay_id,
        original_run_id=run_id,
        tenant_id=episode.tenant_id,
        pipeline_id=original_run_orm.pipeline_id,
        intervention_id=intervention_orm.id,
        status=episode.status.value if hasattr(episode.status, "value") else episode.status,
        swapped_component_type=(
            episode.swapped_component_type.value
            if hasattr(episode.swapped_component_type, "value")
            else episode.swapped_component_type
        ),
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
            "component_type": (
                str(s.component_type.value)
                if s.component_type and hasattr(s.component_type, "value")
                else s.component_type
            ),
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
        evidence_kind=("synthetic_simulation" if episode_orm.is_synthetic else "controlled_replay"),
        manifest_id=manifest_orm.id,
        manifest_hash=manifest_orm.manifest_hash,
        is_pinned=episode_orm.is_pinned,
    )


# ─── POST /v1/runs/{run_id}/finalize ──────────────────────────────────────────

from apps.api.src.schemas import RunFinalizeRequest, RunFinalizeResponse

@router.post(
    "/runs/{run_id}/finalize", response_model=RunFinalizeResponse, status_code=status.HTTP_200_OK
)
async def finalize_run(
    run_id: uuid.UUID,
    request: RunFinalizeRequest,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> RunFinalizeResponse:
    """Finalize a run by transitioning to a terminal state and recording telemetry."""
    result = await db.execute(
        select(RequestRunORM)
        .where(RequestRunORM.id == run_id, RequestRunORM.tenant_id == tenant.id)
        .with_for_update()
    )
    run_orm = result.scalar_one_or_none()
    if run_orm is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Idempotent finalization check
    if run_orm.status in ("COMPLETED", "FAILED", "CANCELLED"):
        # If terminal, just return existing status to be idempotent, 
        # unless conflicting terminal state is passed (then we reject).
        if run_orm.status != request.status:
            raise HTTPException(status_code=409, detail=f"Run already in terminal state {run_orm.status}")
        return RunFinalizeResponse(id=run_id, status=run_orm.status)

    run_orm.status = request.status
    if request.error_type:
        run_orm.error_type = request.error_type
    if request.error_message:
        run_orm.error_message = request.error_message
    if request.reliability_score is not None:
        run_orm.reliability_score = request.reliability_score
    if request.reliability_vector:
        run_orm.reliability_vector = request.reliability_vector
    if request.total_tokens is not None:
        if request.total_tokens < 0:
            raise HTTPException(status_code=422, detail="total_tokens cannot be negative")
        run_orm.total_tokens = request.total_tokens
    if request.total_cost_usd is not None:
        if request.total_cost_usd < 0:
            raise HTTPException(status_code=422, detail="total_cost_usd cannot be negative")
        run_orm.total_cost_usd = request.total_cost_usd
    if request.total_latency_ms is not None:
        if request.total_latency_ms < 0:
            raise HTTPException(status_code=422, detail="total_latency_ms cannot be negative")
        run_orm.total_latency_ms = request.total_latency_ms

    run_orm.completed_at = datetime.now(UTC)

    await db.flush()

    return RunFinalizeResponse(id=run_id, status=run_orm.status)
