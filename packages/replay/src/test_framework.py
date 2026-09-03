"""
DriftGuard-X v2 — Canary Propagation & Replay Test Framework
PRIVATE — All Rights Reserved.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBStep, BCRBStepStatus, ReplayCost, RecoveryEffect, ContaminationState, CounterfactualSupport
from packages.contracts.src.models import ComponentType, _utcnow, ReplayStateManifest
from packages.isolation.src.isolator import QuarantineRule

from apps.api.src.models import RequestRunORM, TraceArtifactORM, ReplayStateManifestORM

from packages.replay.src.engine import ReplayEngine, VersionRegistry
from packages.contracts.src.recovery_models import InterventionSpec
from packages.contracts.src.models import RequestRun, TraceArtifact, ComponentVersion


class CanaryTestFramework:
    """
    Executes canary interventions in an isolated replay environment to validate
    property invariants before changes hit production.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def execute_canary(self, candidate: BCRBCandidate, original_run_id: str, session_id: str, db: AsyncSession = None) -> BCRBStep:
        """
        Run the candidate in an isolated replay to validate its utility.
        """
        replay_id = uuid.uuid4()
        start = _utcnow()

        # If no DB session is provided, we cannot run real replay
        if db is None:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="Replay execution state manifests unavailable for comparison (No DB provided)."
            )

        run_id_uuid = uuid.UUID(original_run_id)
        tenant_id_uuid = uuid.UUID(self.tenant_id)

        # 1. Fetch manifest
        manifest_result = await db.execute(
            select(ReplayStateManifestORM).where(
                ReplayStateManifestORM.run_id == run_id_uuid,
                ReplayStateManifestORM.tenant_id == tenant_id_uuid,
            )
        )
        manifest_orm = manifest_result.scalar_one_or_none()

        if not manifest_orm:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="INSUFFICIENT_EVIDENCE: ReplayStateManifest missing."
            )

        # Build Domain Manifest
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

        # Check contamination
        if not manifest_contract.is_fully_pinned():
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="CONTAMINATED: Original manifest is not fully pinned."
            )

        # 2. Fetch Original Run
        run_result = await db.execute(
            select(RequestRunORM).where(
                RequestRunORM.id == run_id_uuid,
                RequestRunORM.tenant_id == tenant_id_uuid,
            )
        )
        original_run_orm = run_result.scalar_one_or_none()
        
        if not original_run_orm:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="INSUFFICIENT_EVIDENCE: Original run missing."
            )

        original_run_contract = RequestRun(
            id=original_run_orm.id,
            tenant_id=original_run_orm.tenant_id,
            pipeline_id=original_run_orm.pipeline_id,
            trace_id=original_run_orm.trace_id,
            status=original_run_orm.status,
            created_at=original_run_orm.created_at,
            duration_ms=original_run_orm.duration_ms,
            error_message=original_run_orm.error_message,
        )

        # 3. Fetch Trace Artifact
        trace_result = await db.execute(
            select(TraceArtifactORM).where(
                TraceArtifactORM.run_id == run_id_uuid,
            )
        )
        trace_orm = trace_result.scalar_one_or_none()

        if not trace_orm:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="INSUFFICIENT_EVIDENCE: Original trace missing."
            )

        original_trace = TraceArtifact(
            id=trace_orm.id,
            run_id=trace_orm.run_id,
            tenant_id=tenant_id_uuid,
            pipeline_id=original_run_orm.pipeline_id,
            spans=[],
            created_at=trace_orm.created_at,
        )

        # 4. Serialize candidate to InterventionSpec
        spec = InterventionSpec(
            target_component=candidate.component_type,
            intervention_type=candidate.intervention_type,
        )

        import hashlib
        intervention_hash = hashlib.sha256(f"{spec.target_component}:{spec.intervention_type}".encode("utf-8")).hexdigest()

        registry = VersionRegistry()
        to_version = ComponentVersion(
            id=uuid.uuid4(),
            component_type=ComponentType(spec.target_component),
            version_tag="replay-intervention",
            config_hash=intervention_hash
        )
        registry.register(to_version)

        engine = ReplayEngine(registry)

        try:
            episode, replay_trace = engine.execute_replay(
                original_run=original_run_contract,
                original_trace=original_trace,
                intervention=spec,
                replay_version=to_version,
                original_reliability_vector=original_run_orm.reliability_vector or {},
                seed=42,
                manifest=manifest_contract,
            )
        except Exception as e:
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason=f"Replay execution failed: {str(e)}"
            )

        # 5. Calculate evidence
        from packages.contracts.src.evidence import RecoveryEvidenceKind

        # Populate counterfactual support
        candidate.causal_evidence.counterfactual_support = CounterfactualSupport(
            baseline_available=True,
            intervention_available=True,
            negative_control_available=False,
            alternative_intervention_available=False,
            repeated_replay_count=1
        )
        
        candidate.causal_evidence.evidence_provenance = episode.evidence_kind.value

        # Gating: Reject synthetic/mock evidence for posterior update
        if episode.evidence_kind in (
            RecoveryEvidenceKind.SYNTHETIC_DEMO,
            RecoveryEvidenceKind.TEST_FIXTURE,
            RecoveryEvidenceKind.SYNTHETIC_SIMULATION
        ):
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.FAILED,
                replay_episode_id=episode.replay_id,
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason=f"SYNTHETIC_EVIDENCE_ONLY: Provenance is {episode.evidence_kind.value}."
            )

        # Map actual cost from episode
        api_cost = getattr(episode, "cost_usd", None)
        if api_cost is not None and api_cost > 0.0:
            cost_incurred = ReplayCost(
                measurement_status="ACTUAL",
                total_cost=api_cost,
                api_cost=api_cost
            )
        else:
            cost_incurred = ReplayCost(
                measurement_status="UNAVAILABLE",
                total_cost=0.0
            )

        # Compute recovery effect
        original_rv = original_run_orm.reliability_vector or {}
        new_rv = episode.reliability_vector or {}
        
        orig_score = sum(original_rv.values()) / max(len(original_rv), 1) if original_rv else 0.0
        new_score = sum(new_rv.values()) / max(len(new_rv), 1) if new_rv else 0.0
        
        if new_rv:
            recovery_effect = RecoveryEffect(reliability_delta=new_score - orig_score)
        else:
            recovery_effect = None

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
            decision_reason="CLEAN: Measured via actual ReplayEngine execution." if recovery_effect else "INSUFFICIENT_EVIDENCE: Replay executed but reliability missing."
        )

    def validate_quarantine(self, rule: QuarantineRule, original_run_id: str) -> bool:
        """
        Ensure a quarantine rule doesn't cause cascading failures in the topology.
        Returns True if safe to apply.
        """
        raise NotImplementedError("Test framework cannot validate production quarantines. Fabricating quarantine confirmation is forbidden.")
