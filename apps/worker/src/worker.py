"""
DriftGuard-X v2 — Background Worker
PRIVATE — All Rights Reserved.

ARQ worker process and durable background job execution.
Handles replay, graph construction, BCRB diagnosis, benchmarks, and recovery.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from arq.connections import RedisSettings
from arq.typing import WorkerSettingsBase
from sqlalchemy import select, update

from apps.api.src.database import AsyncSessionLocal
from apps.api.src.models import BackgroundJobORM

log = structlog.get_logger()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _mark_running(session, job_uuid: uuid.UUID) -> None:
    await session.execute(
        update(BackgroundJobORM)
        .where(BackgroundJobORM.id == job_uuid)
        .values(status="running", started_at=datetime.now(UTC))
    )
    await session.commit()


async def _mark_completed(session, job_uuid: uuid.UUID, result: dict) -> None:
    current_job = await session.get(BackgroundJobORM, job_uuid)
    if current_job and current_job.status != "cancelled":
        current_job.status = "completed"
        current_job.result_json = result
        current_job.completed_at = datetime.now(UTC)
        await session.commit()


async def _mark_failed(session, job_uuid: uuid.UUID, exc: Exception) -> None:
    current_job = await session.get(BackgroundJobORM, job_uuid)
    if current_job:
        current_job.status = "failed"
        current_job.error_message = str(exc)
        current_job.completed_at = datetime.now(UTC)
        await session.commit()


# ─── Healthcheck ──────────────────────────────────────────────────────────────


async def worker_healthcheck(ctx: dict[str, Any]) -> dict[str, str]:
    """A side-effect-free job used only to verify queue execution."""
    log.info("worker.healthcheck")
    return {"status": "ok"}


# ─── Recovery Diagnosis (legacy entrypoint) ───────────────────────────────────


async def run_recovery_diagnosis(
    ctx: dict[str, Any],
    job_id: str,
    tenant_id: str,
    run_id: str,
    failure_symptom: str,
    invocations_data: list[dict],
) -> dict[str, Any]:
    """Execute the recovery loop in the background."""
    from apps.api.src.database import async_session_maker
    from apps.api.src.models import JobORM
    from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
    from packages.contracts.src.agent_models import AgentInvocation

    log.info("Starting run_recovery_diagnosis", job_id=job_id, run_id=run_id)

    invocations = [AgentInvocation(**inv) for inv in invocations_data]

    async with async_session_maker() as db:
        from sqlalchemy import select

        job_result = await db.execute(select(JobORM).where(JobORM.id == uuid.UUID(job_id)))
        job_orm = job_result.scalar_one_or_none()
        if job_orm:
            job_orm.status = "RUNNING"
            job_orm.started_at = datetime.now(UTC)
            await db.commit()

        try:
            pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)
            approval_req = await pipeline.execute_recovery_loop(
                run_id, invocations, failure_symptom, db
            )
            await db.commit()

            if job_orm:
                job_orm.status = "SUCCEEDED"
                job_orm.completed_at = datetime.now(UTC)
                if (
                    approval_req
                    and getattr(approval_req, "status", None) == "INSUFFICIENT_EVIDENCE"
                ):
                    job_orm.result = {
                        "status": "INSUFFICIENT_EVIDENCE",
                        "next_action": getattr(approval_req, "next_action", None),
                        "highest_posterior": getattr(approval_req, "highest_posterior", None),
                        "threshold": getattr(approval_req, "threshold", None),
                        "highest_candidate_component": str(
                            getattr(approval_req, "highest_candidate_component", None)
                        ),
                    }
                else:
                    job_orm.result = (
                        {"approval_request_id": str(approval_req.id)}
                        if approval_req
                        else {"status": "no_candidates"}
                    )
                await db.commit()

            if approval_req and getattr(approval_req, "status", None) == "INSUFFICIENT_EVIDENCE":
                return job_orm.result

            return {
                "status": "success",
                "approval_request_id": str(approval_req.id) if approval_req else None,
            }

        except Exception as e:
            await db.rollback()
            log.exception("Recovery diagnosis failed", job_id=job_id, exc_info=e)
            if job_orm:
                job_orm.status = "FAILED"
                job_orm.completed_at = datetime.now(UTC)
                job_orm.error = str(e)
                await db.commit()
            raise e


# ─── Replay Worker ────────────────────────────────────────────────────────────


async def execute_replay_job(
    ctx: dict[str, Any], job_id: str, tenant_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute a counterfactual replay episode against the real ReplayEngine.

    Payload expected keys:
        run_id         (str) — UUID of the original run
        intervention_id (str) — UUID of the approved InterventionSpec
        seed           (int, optional) — random seed, default 42
    """
    log.info("worker.execute_replay_job", job_id=job_id, tenant_id=tenant_id)
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await _mark_running(session, job_uuid)

    try:
        run_id_str = payload.get("run_id")
        intervention_id_str = payload.get("intervention_id")
        seed = int(payload.get("seed", 42))

        if not run_id_str:
            raise ValueError("Replay payload missing required field: run_id")
        if not intervention_id_str:
            raise ValueError("Replay payload missing required field: intervention_id")

        run_uuid = uuid.UUID(run_id_str)
        intervention_uuid = uuid.UUID(intervention_id_str)

        async with AsyncSessionLocal() as session:
            from apps.api.src.models import (
                InterventionORM,
                ReplayEpisodeORM,
                ReplayStateManifestORM,
                RequestRunORM,
                TraceArtifactORM,
            )
            from packages.contracts.src.models import (
                ComponentType,
                ComponentVersion,
                ReplayStateManifest,
                RequestRun,
                SpanRecord,
                TraceArtifact,
            )
            from packages.contracts.src.recovery_models import InterventionSpec
            from packages.replay.src.divergence_validator import DynamicCausalDivergenceValidator
            from packages.replay.src.engine import ReplayEngine, VersionRegistry

            # 1. Load run — validate tenant
            run_orm = await session.get(RequestRunORM, run_uuid)
            if run_orm is None:
                raise ValueError(f"Run not found: {run_id_str}")
            if run_orm.tenant_id != tenant_uuid:
                raise PermissionError(f"Run {run_id_str} does not belong to tenant {tenant_id}")

            # 2. Load trace
            trace_result = await session.execute(
                select(TraceArtifactORM).where(TraceArtifactORM.run_id == run_uuid)
            )
            trace_orm = trace_result.scalar_one_or_none()
            if trace_orm is None:
                raise ValueError(f"Trace not found for run: {run_id_str}")

            # 3. Load manifest — validate pinning
            manifest_result = await session.execute(
                select(ReplayStateManifestORM).where(ReplayStateManifestORM.run_id == run_uuid)
            )
            manifest_orm = manifest_result.scalar_one_or_none()
            if manifest_orm is None:
                raise ValueError(f"ReplayStateManifest not found for run: {run_id_str}")

            # 4. Load intervention
            intervention_orm = await session.get(InterventionORM, intervention_uuid)
            if intervention_orm is None:
                raise ValueError(f"Intervention not found: {intervention_id_str}")

            # 5. Reconstruct domain objects
            spans = [SpanRecord(**s) for s in (trace_orm.spans_json or [])]
            original_trace = TraceArtifact(
                id=trace_orm.id,
                run_id=trace_orm.run_id,
                tenant_id=trace_orm.tenant_id,
                pipeline_id=trace_orm.pipeline_id,
                spans=spans,
                root_span_id=trace_orm.root_span_id,
                total_span_count=trace_orm.total_span_count,
            )

            original_run = RequestRun(
                id=run_orm.id,
                tenant_id=run_orm.tenant_id,
                pipeline_id=run_orm.pipeline_id,
                status=run_orm.status,
                request_hash=run_orm.request_hash or "",
                response_hash=run_orm.response_hash or "",
                reliability_score=run_orm.reliability_score or 0.0,
                reliability_vector=run_orm.reliability_vector or {},
                total_latency_ms=run_orm.total_latency_ms or 0.0,
                total_tokens=run_orm.total_tokens or 0,
                total_cost_usd=run_orm.total_cost_usd or 0.0,
                seed=run_orm.seed or seed,
                evidence_class=run_orm.evidence_class,
            )

            manifest = ReplayStateManifest(
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
                retriever_settings=manifest_orm.retriever_settings or {},
                retrieved_chunk_ids=manifest_orm.retrieved_chunk_ids or [],
                embedding_provider=manifest_orm.embedding_provider,
                embedding_model_id=manifest_orm.embedding_model_id,
                embedding_model_version=manifest_orm.embedding_model_version,
                embedding_vector_dimension=manifest_orm.embedding_vector_dimension,
                embedding_config_hash=manifest_orm.embedding_config_hash,
                vector_index_snapshot_id=manifest_orm.vector_index_snapshot_id,
                tool_schemas_hash=manifest_orm.tool_schemas_hash,
                policy_config_hash=manifest_orm.policy_config_hash,
                memory_snapshot_id=manifest_orm.memory_snapshot_id,
                random_seed=manifest_orm.random_seed,
                generation_parameters=manifest_orm.generation_parameters or {},
                container_image_digest=manifest_orm.container_image_digest,
                dependency_lockfile_hash=manifest_orm.dependency_lockfile_hash,
                trace_root_hash=manifest_orm.trace_root_hash,
                manifest_hash=manifest_orm.manifest_hash,
            )

            # 6. Validate pinning — gate must fail closed
            if not manifest.is_fully_pinned():
                raise ValueError(
                    "Replay refused: manifest is not fully pinned. "
                    "Cannot safely execute a replay without complete provenance."
                )

            # 7. Build version registry from trace spans
            registry = VersionRegistry()
            intervention_spec = InterventionSpec(
                target_component=ComponentType(intervention_orm.target_component_type),
                current_version=intervention_orm.from_version_tag,
                candidate_version=intervention_orm.to_version_tag,
                intervention_type=intervention_orm.intervention_type,
            )

            # Register the replay version (the new one to test)
            replay_cv = ComponentVersion(
                component_type=ComponentType(intervention_orm.target_component_type),
                version_tag=intervention_orm.to_version_tag,
                description=f"Replay candidate: {intervention_orm.to_version_tag}",
            )
            registry.register(replay_cv)

            # Register original versions from trace spans
            for span in spans:
                if span.component_version_id and span.component_type:
                    orig_cv = ComponentVersion(
                        id=span.component_version_id,
                        component_type=span.component_type,
                        version_tag=span.component_version_tag or "pinned",
                        description="Pinned from original trace",
                    )
                    registry.register(orig_cv)

            # 8. Execute replay
            engine = ReplayEngine(registry)
            original_reliability_vector = run_orm.reliability_vector or {}

            episode, replay_trace = engine.execute_replay(
                original_run=original_run,
                original_trace=original_trace,
                intervention=intervention_spec,
                replay_version=replay_cv,
                original_reliability_vector=original_reliability_vector,
                seed=seed,
                manifest=manifest,
            )

            # 9. Run divergence validation using span-based snapshots
            from packages.replay.src.divergence_validator import (
                ExecutionSnapshot,
            )

            orig_snapshot = ExecutionSnapshot.from_spans(
                [s.model_dump() for s in original_trace.spans]
            )
            replay_trace_spans = (
                [s.model_dump() for s in replay_trace.spans]
                if replay_trace and replay_trace.spans
                else []
            )
            replay_snapshot = ExecutionSnapshot.from_spans(replay_trace_spans)

            # Build a minimal envelope: intervened node is the swapped component's span
            intervened_ids = [
                s.span_id
                for s in original_trace.spans
                if str(s.component_type) == str(intervention_orm.target_component_type)
            ]
            # All downstream spans (those after the intervention in pipeline order) are allowed descendants
            found_intervention = False
            allowed_descendants: list[str] = []
            for s in original_trace.spans:
                if str(s.component_type) == str(intervention_orm.target_component_type):
                    found_intervention = True
                    continue
                if found_intervention:
                    allowed_descendants.append(s.span_id)

            class _SimpleEnvelope:
                intervened_variables = intervened_ids
                allowed_causal_descendants = allowed_descendants
                forbidden_divergence_nodes: list[str] = []
                frozen_variables: dict[str, str] = {}
                constraints: dict[str, Any] = {}

            validator = DynamicCausalDivergenceValidator()
            divergence_report = validator.validate(
                orig_snapshot, replay_snapshot, _SimpleEnvelope()
            )

            # 10. Persist ReplayEpisodeORM
            episode_orm = ReplayEpisodeORM(
                id=episode.replay_id,
                original_run_id=run_uuid,
                tenant_id=tenant_uuid,
                pipeline_id=run_orm.pipeline_id,
                intervention_id=intervention_uuid,
                manifest_id=manifest_orm.id,
                status="completed",
                is_pinned=True,
                swapped_component_type=str(episode.swapped_component_type.value),
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
                completed_at=datetime.now(UTC),
                evidence_class=str(episode.evidence_class.value) if hasattr(episode.evidence_class, "value") else str(episode.evidence_class),
                replay_mode="real",
            )
            session.add(episode_orm)
            await session.commit()

            result = {
                "status": "completed",
                "run_id": run_id_str,
                "replay_id": str(episode.replay_id),
                "episodes_executed": 1,
                "divergence_observed": not divergence_report.valid,
                "reliability_improvement": episode.reliability_improvement,
                "evidence_kind": "REAL_REPLAY",
            }

        async with AsyncSessionLocal() as session:
            await _mark_completed(session, job_uuid, result)

        return result

    except Exception as exc:
        log.exception("worker.execute_replay_job.failed", job_id=job_id, error=str(exc))
        async with AsyncSessionLocal() as session:
            await _mark_failed(session, job_uuid, exc)
        raise


# ─── Graph Construction Worker ────────────────────────────────────────────────


async def execute_graph_construction_job(
    ctx: dict[str, Any], job_id: str, tenant_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """
    Build a causal graph from a trace artifact using the real GraphBuilder.

    Payload expected keys:
        run_id    (str) — UUID of the run whose trace to build a graph from
        trace_id  (str, optional) — UUID of the TraceArtifact (resolved from run_id if omitted)
    """
    log.info("worker.execute_graph_construction_job", job_id=job_id, tenant_id=tenant_id)
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await _mark_running(session, job_uuid)

    try:
        run_id_str = payload.get("run_id")
        if not run_id_str:
            raise ValueError("Graph construction payload missing required field: run_id")

        run_uuid = uuid.UUID(run_id_str)

        async with AsyncSessionLocal() as session:
            from apps.api.src.models import RequestRunORM, TraceArtifactORM
            from apps.api.src.models_graph import CausalGraphORM, GraphEdgeORM
            from packages.contracts.src.models import SpanRecord, TraceArtifact
            from packages.graph.src.builder import BUILDER_VERSION, GraphBuilder
            from packages.trace_sdk.src.tracer import hash_payload

            # 1. Load run — validate tenant
            run_orm = await session.get(RequestRunORM, run_uuid)
            if run_orm is None:
                raise ValueError(f"Run not found: {run_id_str}")
            if run_orm.tenant_id != tenant_uuid:
                raise PermissionError(f"Run {run_id_str} does not belong to tenant {tenant_id}")

            # 2. Load trace
            trace_result = await session.execute(
                select(TraceArtifactORM).where(TraceArtifactORM.run_id == run_uuid)
            )
            trace_orm = trace_result.scalar_one_or_none()
            if trace_orm is None:
                raise ValueError(f"Trace not found for run: {run_id_str}")

            # 3. Reconstruct domain object
            spans = [SpanRecord(**s) for s in (trace_orm.spans_json or [])]
            trace = TraceArtifact(
                id=trace_orm.id,
                run_id=trace_orm.run_id,
                tenant_id=trace_orm.tenant_id,
                pipeline_id=trace_orm.pipeline_id,
                spans=spans,
                root_span_id=trace_orm.root_span_id,
                total_span_count=trace_orm.total_span_count,
            )

            # 4. Compute trace digest
            trace_digest = hash_payload([s.model_dump() for s in spans])

            # 5. Build graph (idempotent — skip if already built)
            graph_hash = hashlib.sha256(
                f"{tenant_id}:{run_id_str}:{trace_digest}:{BUILDER_VERSION}".encode()
            ).hexdigest()

            existing = await session.get(CausalGraphORM, graph_hash)
            if existing is not None:
                result = {
                    "status": "completed",
                    "run_id": run_id_str,
                    "graph_hash": graph_hash,
                    "nodes_count": len(existing.nodes_json),
                    "edges_count": len(existing.edges_json),
                    "cache_hit": True,
                }
            else:
                # Use the in-memory version registry (graph builder reads from it)
                from packages.replay.src.engine import VersionRegistry as LocalRegistry

                local_registry = LocalRegistry()

                class _RegistryAdapter:
                    """Adapts LocalRegistry to satisfy ContractVersionRegistry interface."""

                    def __init__(self, inner):
                        self._inner = inner

                    async def get_version(self, tenant_id, version_id):
                        return self._inner.get(version_id)

                adapted_registry = _RegistryAdapter(local_registry)
                builder = GraphBuilder(version_registry=adapted_registry)
                graph = await builder.build(trace)

                nodes_json = [n.model_dump(mode="json") for n in graph.nodes.values()]
                edges_json = [e.model_dump(mode="json") for e in graph.edges]

                graph_orm = CausalGraphORM(
                    graph_hash=graph_hash,
                    tenant_id=str(tenant_uuid),
                    run_id=run_id_str,
                    trace_digest=trace_digest,
                    builder_version=BUILDER_VERSION,
                    nodes_json=nodes_json,
                    edges_json=edges_json,
                    created_at=datetime.now(UTC),
                )
                session.add(graph_orm)

                # Persist relational edges for CTE traversal
                for edge in graph.edges:
                    edge_pk = f"{graph_hash}:{edge.id}"
                    edge_orm = GraphEdgeORM(
                        id=edge_pk,
                        graph_hash=graph_hash,
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        edge_type=(
                            str(edge.type.value) if hasattr(edge.type, "value") else str(edge.type)
                        ),
                        label=edge.label,
                        properties_json=edge.properties or {},
                    )
                    session.add(edge_orm)

                await session.commit()

                result = {
                    "status": "completed",
                    "run_id": run_id_str,
                    "graph_hash": graph_hash,
                    "nodes_count": len(nodes_json),
                    "edges_count": len(edges_json),
                    "cache_hit": False,
                }

        async with AsyncSessionLocal() as session:
            await _mark_completed(session, job_uuid, result)

        return result

    except Exception as exc:
        log.exception("worker.execute_graph_construction_job.failed", job_id=job_id, error=str(exc))
        async with AsyncSessionLocal() as session:
            await _mark_failed(session, job_uuid, exc)
        raise


# ─── BCRB Diagnosis Worker ────────────────────────────────────────────────────


async def execute_bcrb_diagnosis_job(
    ctx: dict[str, Any], job_id: str, tenant_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """
    Run sequential BCRB diagnosis against the real BCRBOrchestrator.

    Payload expected keys:
        run_id           (str)  — UUID of the failing run
        failure_symptom  (str)  — human-readable failure description
        budget_usd       (float, optional) — max budget, default 5.0
    """
    log.info("worker.execute_bcrb_diagnosis_job", job_id=job_id, tenant_id=tenant_id)
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await _mark_running(session, job_uuid)

    try:
        run_id_str = payload.get("run_id", "")
        failure_symptom = payload.get("failure_symptom", "unknown_failure")
        budget_usd = float(payload.get("budget_usd", 5.0))

        if not run_id_str:
            raise ValueError("BCRB payload missing required field: run_id")

        run_uuid_val = uuid.UUID(run_id_str)

        async with AsyncSessionLocal() as session:
            from apps.api.src.models import RequestRunORM, SpanRecordORM
            from packages.bcrb.src.orchestrator import BCRBOrchestrator
            from packages.contracts.src.agent_models import AgentInvocation
            from packages.contracts.src.bcrb_models import BCRBSession, StoppingCondition

            # 1. Load run — validate tenant
            run_orm = await session.get(RequestRunORM, run_uuid_val)
            if run_orm is None:
                raise ValueError(f"Run not found: {run_id_str}")
            if run_orm.tenant_id != tenant_uuid:
                raise PermissionError(f"Run {run_id_str} does not belong to tenant {tenant_id}")

            # 2. Load spans to reconstruct agent invocations
            spans_result = await session.execute(
                select(SpanRecordORM).where(SpanRecordORM.run_id == run_uuid_val)
            )
            span_orms = spans_result.scalars().all()

            invocations = []
            for span in span_orms:
                if span.component_type:
                    try:
                        inv = AgentInvocation(
                            invocation_id=str(span.id),
                            component_type=span.component_type,
                            version_tag=span.component_version_tag or "unknown",
                            latency_ms=span.latency_ms or 0.0,
                            is_error=bool(span.error_type),
                            input_hash=span.input_hash or "",
                            output_hash=span.output_hash or "",
                            token_count=span.token_count_input or 0,
                        )
                        invocations.append(inv)
                    except Exception:
                        pass  # Skip malformed spans

            # 3. Build BCRB session
            session_obj = BCRBSession(
                session_id=uuid.uuid4(),
                run_id=run_uuid_val,
                tenant_id=tenant_uuid,
                failure_symptom=failure_symptom,
                budget_usd=budget_usd,
            )

            # 4. Execute
            orchestrator = BCRBOrchestrator(tenant_id=tenant_id)
            completed_session = await orchestrator.execute_session(
                session_obj, invocations, failure_symptom, db=session
            )

            stopping = completed_session.stopping_condition_met
            if stopping is None:
                stopping = StoppingCondition.ALL_SAFE_CANDIDATES_TESTED

            # 5. Determine diagnosed root cause from posterior
            top_candidate = None
            top_posterior = -1.0
            for candidate in completed_session.candidates:
                if candidate.causal_evidence and candidate.causal_evidence.posterior is not None:
                    if candidate.causal_evidence.posterior > top_posterior:
                        top_posterior = candidate.causal_evidence.posterior
                        top_candidate = candidate

            if top_candidate is None:
                diagnosed_root_cause = "INSUFFICIENT_EVIDENCE"
                confidence = 0.0
            else:
                diagnosed_root_cause = (
                    top_candidate.component_type.value
                    if hasattr(top_candidate.component_type, "value")
                    else str(top_candidate.component_type)
                )
                confidence = top_posterior

            result = {
                "status": "completed",
                "run_id": run_id_str,
                "diagnosed_root_cause": diagnosed_root_cause,
                "confidence": confidence,
                "stopping_condition": (
                    stopping.value if hasattr(stopping, "value") else str(stopping)
                ),
                "total_spent_usd": completed_session.total_spent_usd,
                "steps_executed": len(completed_session.steps),
                "posterior_history": [
                    {
                        "candidate_id": str(c.candidate_id),
                        "component_type": (
                            c.component_type.value
                            if hasattr(c.component_type, "value")
                            else str(c.component_type)
                        ),
                        "prior": c.causal_evidence.prior if c.causal_evidence else None,
                        "posterior": c.causal_evidence.posterior if c.causal_evidence else None,
                    }
                    for c in completed_session.candidates
                ],
            }

        async with AsyncSessionLocal() as session:
            await _mark_completed(session, job_uuid, result)

        return result

    except Exception as exc:
        log.exception("worker.execute_bcrb_diagnosis_job.failed", job_id=job_id, error=str(exc))
        async with AsyncSessionLocal() as session:
            await _mark_failed(session, job_uuid, exc)
        raise


# ─── Recovery Worker ──────────────────────────────────────────────────────────


async def execute_recovery_job(
    ctx: dict[str, Any], job_id: str, tenant_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute the end-to-end recovery sequence against the real EndToEndRecoveryPipeline.

    Payload expected keys:
        run_id           (str) — UUID of the run to recover
        failure_symptom  (str) — description of the failure
        invocations_data (list[dict], optional) — serialised AgentInvocation list
    """
    log.info("worker.execute_recovery_job", job_id=job_id, tenant_id=tenant_id)
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await _mark_running(session, job_uuid)

    try:
        run_id_str = payload.get("run_id", "")
        failure_symptom = payload.get("failure_symptom", "unknown_failure")
        invocations_data = payload.get("invocations_data", [])

        if not run_id_str:
            raise ValueError("Recovery payload missing required field: run_id")

        from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
        from packages.contracts.src.agent_models import AgentInvocation

        invocations = [AgentInvocation(**inv) for inv in invocations_data]

        async with AsyncSessionLocal() as session:
            from apps.api.src.models import RequestRunORM

            # Validate tenant ownership
            run_orm = await session.get(RequestRunORM, uuid.UUID(run_id_str))
            if run_orm is None:
                raise ValueError(f"Run not found: {run_id_str}")
            if run_orm.tenant_id != tenant_uuid:
                raise PermissionError(f"Run {run_id_str} does not belong to tenant {tenant_id}")

            pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)
            approval_req = await pipeline.execute_recovery_loop(
                run_id_str, invocations, failure_symptom, session
            )
            await session.commit()

        approval_id = str(approval_req.id) if approval_req else None
        result = {
            "status": "completed",
            "action": "recovery",
            "run_id": run_id_str,
            "approval_request_id": approval_id,
            "verification_passed": approval_req is not None,
        }

        async with AsyncSessionLocal() as session:
            await _mark_completed(session, job_uuid, result)

        return result

    except Exception as exc:
        log.exception("worker.execute_recovery_job.failed", job_id=job_id, error=str(exc))
        async with AsyncSessionLocal() as session:
            await _mark_failed(session, job_uuid, exc)
        raise


# ─── ARQ Worker Settings ──────────────────────────────────────────────────────


class WorkerSettings:
    functions = [
        worker_healthcheck,
        execute_replay_job,
        execute_graph_construction_job,
        execute_bcrb_diagnosis_job,
        execute_recovery_job,
        run_recovery_diagnosis,
    ]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # 1 hour


if __name__ == "__main__":
    from arq import run_worker

    log.info("worker.starting", redis_url=REDIS_URL)
    run_worker(cast(type[WorkerSettingsBase], WorkerSettings))
