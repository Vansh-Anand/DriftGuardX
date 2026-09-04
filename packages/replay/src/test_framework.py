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
                replay_episode_id=uuid.uuid4(),
                utility_observed=None,
                cost_incurred=ReplayCost(measurement_status="UNAVAILABLE", total_cost=0.0),
                recovery_effect=None,
                start_time=start,
                end_time=_utcnow(),
                decision_reason="INSUFFICIENT_EVIDENCE: No database session provided."
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
            decision_reason="CLEAN: Measured via actual ReplayEngine execution." if recovery_effect else "INSUFFICIENT_EVIDENCE: Replay executed but reliability missing."
        )

    async def async_validate_quarantine(self, rule, original_run_id: str, db, isolator=None, invariants=None) -> bool:
        """
        Ensure a quarantine rule doesn't cause cascading failures in the topology.
        Returns True if safe to apply (canary succeeds).
        """
        from packages.rag_pipeline.src.agents import AgentPipeline
        from packages.contracts.src.recovery_models import CanaryInvariants
        import time
        import uuid
        
        invariants = invariants or CanaryInvariants()
        
        pipeline = AgentPipeline()
        
        canary_query = "Canary health check"
        canary_tenant = self.tenant_id
        canary_run_id = str(uuid.uuid4())
        
        comp_str = rule.target_component.value if hasattr(rule.target_component, "value") else str(rule.target_component)
        quarantined = {comp_str}
        
        start_time = time.monotonic()
        state = pipeline.run(
            query=canary_query,
            run_id=canary_run_id,
            tenant_id=canary_tenant,
            quarantined_agents=quarantined,
            max_hops=5
        )
        latency_ms = (time.monotonic() - start_time) * 1000
        
        success = True
        if "error" in state.final_response.lower() and "max hops" not in state.final_response.lower():
            success = False
            
        if latency_ms > invariants.max_latency_ms:
            success = False
            
        if not success:
            if isolator and db:
                await isolator.async_remove_quarantine(rule.rule_id, db)
            return False
            
        return True
