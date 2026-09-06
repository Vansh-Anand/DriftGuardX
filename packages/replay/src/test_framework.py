"""
DriftGuard-X v2 — Canary Propagation & Replay Test Framework
PRIVATE — All Rights Reserved.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.models import ReplayStateManifestORM, RequestRunORM, TraceArtifactORM
from packages.contracts.src.bcrb_models import (
    BCRBCandidate,
    BCRBStep,
    BCRBStepStatus,
    ContaminationState,
    CounterfactualSupport,
    RecoveryEffect,
    ReplayCost,
)
from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.models import (
    ComponentType,
    ComponentVersion,
    ReplayStateManifest,
    RequestRun,
    TraceArtifact,
    _utcnow,
)
from packages.contracts.src.recovery_models import InterventionSpec
from packages.replay.src.engine import ReplayEngine, VersionRegistry


class CanaryTestFramework:
    """
    Executes canary interventions in an isolated replay environment to validate
    property invariants before changes hit production.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def execute_canary(
        self,
        candidate: BCRBCandidate,
        original_run_id: str,
        session_id: str,
        db: AsyncSession | None = None,
    ) -> BCRBStep:
        start = _utcnow()
        if db is None:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=None,
                utility_observed=None,
                cost_incurred=None,
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="No DB provided",
            )

        uuid.uuid4()

        manifest_orm = (
            await db.execute(
                select(ReplayStateManifestORM).where(
                    ReplayStateManifestORM.run_id == uuid.UUID(original_run_id)
                )
            )
        ).scalar_one_or_none()
        run_orm = (
            await db.execute(
                select(RequestRunORM).where(RequestRunORM.id == uuid.UUID(original_run_id))
            )
        ).scalar_one_or_none()
        trace_orm = (
            await db.execute(
                select(TraceArtifactORM).where(
                    TraceArtifactORM.run_id == uuid.UUID(original_run_id)
                )
            )
        ).scalar_one_or_none()

        if not manifest_orm or not run_orm or not trace_orm:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=uuid.uuid4(),
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="INSUFFICIENT_EVIDENCE: Required artifacts missing from DB.",
            )

        # Convert ORM to Pydantic models (omitted robust mapping for brevity)
        manifest = ReplayStateManifest.model_construct(
            manifest_id=manifest_orm.id,
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

        run = RequestRun.model_construct(
            run_id=run_orm.id,
            tenant_id=run_orm.tenant_id,
            pipeline_id=run_orm.pipeline_id,
            trace_id=run_orm.trace_id,
            status=run_orm.status,
            created_at=run_orm.created_at,
            duration_ms=run_orm.duration_ms,
            error_message=run_orm.error_message,
            reliability_vector=run_orm.reliability_vector,
            evidence_class=run_orm.evidence_class,
        )

        trace = TraceArtifact.model_construct(
            trace_id=trace_orm.id,
            run_id=trace_orm.run_id,
            payload=trace_orm.payload,
            payload_hash=trace_orm.payload_hash,
            created_at=trace_orm.created_at,
        )

        intervention_spec = InterventionSpec(
            target_component=candidate.component_type,
            intervention_type=candidate.intervention_type,
            target_version="latest",
            params={},
        )

        engine = ReplayEngine(version_registry=VersionRegistry())

        cv = ComponentVersion(
            id=uuid.uuid4(),
            component_type=ComponentType(candidate.component_type),
            version_tag="latest",
            image_digest="latest",
            config_hash="default_config",
            created_at=_utcnow(),
        )

        episode, error = engine.execute_replay(
            original_run=run,
            original_trace=trace,
            intervention=intervention_spec,
            replay_version=cv,
            original_reliability_vector=run.reliability_vector,
            manifest=manifest,
        )

        if not episode:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=uuid.uuid4(),
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="FAILED", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason=f"INSUFFICIENT_EVIDENCE: Replay failed - {error}",
            )

        cost_incurred = ReplayCost(
            measurement_status="OK",
            total_cost=episode.cost_usd,
            evidence_kind=(
                episode.evidence_class.value
                if hasattr(episode.evidence_class, "value")
                else str(episode.evidence_class)
            ),
        )
        print("EPISODE TYPE:", type(episode))
        print("IS SYNTHETIC:", getattr(episode, "is_synthetic", False))
        print("EVIDENCE CLASS:", getattr(episode, "evidence_class", None))

        if getattr(episode, "is_synthetic", False) or getattr(episode, "evidence_class", None) in (
            EvidenceClassification.SYNTHETIC_SIMULATION,
            "SYNTHETIC_SIMULATION",
        ):
            candidate.causal_evidence.evidence_provenance = (
                EvidenceClassification.SYNTHETIC_SIMULATION
            )
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=episode.replay_id,
                utility_observed=None,
                cost_incurred=cost_incurred,
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="SYNTHETIC_EVIDENCE_ONLY: Synthetic demonstrations are not valid causal evidence.",
            )

        reliability_delta = 0.0
        if "reliability" in episode.reliability_vector and "reliability" in run.reliability_vector:
            reliability_delta = (
                episode.reliability_vector["reliability"] - run.reliability_vector["reliability"]
            )

        recovery_effect = RecoveryEffect(
            success=reliability_delta > 0,
            reliability_delta=reliability_delta,
            contamination=ContaminationState.CLEAN,
            counterfactual=CounterfactualSupport(intervention_available=True),
        )

        return BCRBStep(
            step_id=uuid.uuid4(),
            session_id=uuid.UUID(session_id),
            candidate_id=candidate.candidate_id,
            status=BCRBStepStatus.COMPLETED if recovery_effect else BCRBStepStatus.FAILED,
            replay_episode_id=episode.replay_id,
            utility_observed=recovery_effect.reliability_delta if recovery_effect else None,
            cost_incurred=cost_incurred,
            recovery_effect=recovery_effect,
            start_time=start,
            end_time=_utcnow(),
            decision_reason=(
                "CLEAN: Measured via actual ReplayEngine execution."
                if recovery_effect
                else "INSUFFICIENT_EVIDENCE: Replay executed but reliability missing."
            ),
        )

    async def async_validate_quarantine(
        self, rule, original_run_id: str, db, isolator=None, invariants=None
    ) -> bool:
        """
        Ensure a quarantine rule doesn't cause cascading failures in the topology.
        Returns True if safe to apply (canary succeeds).
        """
        import time
        import uuid

        from packages.contracts.src.recovery_models import CanaryInvariants
        from packages.rag_pipeline.src.agents import AgentPipeline

        invariants = invariants or CanaryInvariants()

        pipeline = AgentPipeline()

        canary_query = "Canary health check"
        canary_tenant = self.tenant_id
        canary_run_id = str(uuid.uuid4())

        comp_str = (
            rule.target_component.value
            if hasattr(rule.target_component, "value")
            else str(rule.target_component)
        )
        quarantined = {comp_str}

        start_time = time.monotonic()
        state = pipeline.run(
            query=canary_query,
            run_id=canary_run_id,
            tenant_id=canary_tenant,
            quarantined_agents=quarantined,
            max_hops=5,
        )
        latency_ms = (time.monotonic() - start_time) * 1000

        success = True
        if (
            "error" in state.final_response.lower()
            and "max hops" not in state.final_response.lower()
        ):
            success = False

        if latency_ms > invariants.max_latency_ms:
            success = False

        if invariants.require_safety_policy and "policy violation" in state.final_response.lower():
            success = False

        reliability = state.read_memory("reliability_score") or 1.0
        if reliability < invariants.min_reliability:
            success = False

        if not success:
            if isolator and db:
                await isolator.async_remove_quarantine(rule.rule_id, db)
            return False

        return True
