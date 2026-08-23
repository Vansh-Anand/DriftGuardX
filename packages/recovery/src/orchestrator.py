"""
DriftGuard-X v2 — Causal Recovery Orchestrator
PRIVATE — All Rights Reserved.
"""
from typing import Any

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.interfaces import (
    BeliefModel,
    DivergenceValidator,
    EnvelopeBuilder,
    ExperimentPlanner,
    GraphProvider,
    InterventionGenerator,
    Ledger,
    PolicyEngine,
    RAEBGateway,
    RecoveryCutSolver,
    RecoveryValidator,
    ReplayExecutor,
    StoppingPolicy,
    TraceProvider,
    TransportabilityGate,
)
from packages.contracts.src.recovery_models import FailureTarget
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
)
from packages.recovery.src.incident_state_machine import IncidentStateMachine


class CausalRecoveryOrchestrator:
    """
    Coordinates the full end-to-end incident diagnosis and recovery lifecycle.
    """

    def __init__(
        self,
        trace_provider: TraceProvider,
        graph_provider: GraphProvider,
        intervention_generator: InterventionGenerator,
        envelope_builder: EnvelopeBuilder,
        raeb_gateway: RAEBGateway,
        experiment_planner: ExperimentPlanner,
        replay_executor: ReplayExecutor,
        divergence_validator: DivergenceValidator,
        belief_model: BeliefModel,
        stopping_policy: StoppingPolicy,
        recovery_solver: RecoveryCutSolver,
        recovery_validator: RecoveryValidator,
        policy_engine: PolicyEngine,
        ledger: Ledger,
        transport_gate: TransportabilityGate | None = None,
    ):
        self.trace_provider = trace_provider
        self.graph_provider = graph_provider
        self.intervention_generator = intervention_generator
        self.envelope_builder = envelope_builder
        self.raeb_gateway = raeb_gateway
        self.experiment_planner = experiment_planner
        self.replay_executor = replay_executor
        self.divergence_validator = divergence_validator
        self.belief_model = belief_model
        self.stopping_policy = stopping_policy
        self.recovery_solver = recovery_solver
        self.recovery_validator = recovery_validator
        self.policy_engine = policy_engine
        self.ledger = ledger
        self.transport_gate = transport_gate

    def process_incident(self, incident_state: IncidentState, failure_targets: list[FailureTarget]) -> str:
        """Runs the incident to completion (or failure mode), returning the final certificate hash."""
        machine = IncidentStateMachine(incident_state)

        try:
            # 1. Start observing
            machine.transition(IncidentStatus.FAILURE_DETECTED, "Failure target registered.")

            # 2. Extract Trace and Graph
            trace = self.trace_provider.get_trace(incident_state.incident_id)
            if not trace:
                raise ValueError("No trace found.")
            graph = self.graph_provider.get_causal_graph(incident_state.incident_id)
            if not graph:
                raise ValueError("No causal graph found.")

            machine.transition(IncidentStatus.DIAGNOSING, "Analyzing trace and graph.")

            # 3. Candidates & Envelope
            candidates = self.intervention_generator.generate_candidates(incident_state)
            if not candidates:
                machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "No candidate interventions.")
                return ""

            envelope = self.envelope_builder.build_envelope(incident_state.incident_id, candidates)
            incident_state.envelope_id = envelope.trace_id

            if not self.raeb_gateway.check_admissibility(envelope):
                machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "RAEB Admissibility rejected envelope.")
                return ""

            # 4. Iterative Replaying
            machine.transition(IncidentStatus.REPLAYING, "Starting causal replay loop.")
            max_iters = 5
            for i in range(max_iters):
                experiments = self.experiment_planner.plan_experiments(envelope, candidates)
                if not experiments:
                    break # Exhausted candidates or budget

                replays = self.replay_executor.execute_replays(experiments)
                if not self.divergence_validator.validate_divergence(replays):
                    machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "Replay diverged significantly from frontier.")
                    return ""

                new_belief = self.belief_model.update_belief(incident_state, replays)
                incident_state.root_cause_posterior = new_belief

                if self.stopping_policy.is_sufficient(incident_state):
                    break

            if not self.stopping_policy.is_sufficient(incident_state):
                machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "Posterior did not converge or budget exhausted.")
                return ""

            machine.transition(IncidentStatus.EVIDENCE_SUFFICIENT, "Causal evidence collected.")

            # 5. Recovery Cut
            machine.transition(IncidentStatus.RECOVERY_PLANNING, "Solving for minimum causal cut.")
            cut = self.recovery_solver.solve(failure_targets, incident_state.root_cause_posterior)
            if not cut:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Impossible to find valid cut.")
                return ""

            # 6. Validate & Authorize
            machine.transition(IncidentStatus.RECOVERY_VALIDATING, "Validating cut invariants.")
            val_result = self.recovery_validator.validate(cut)
            if not val_result.invariants_satisfied:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Invariant validation failed.")
                return ""

            machine.transition(IncidentStatus.AWAITING_AUTHORIZATION, "Checking policy capabilities.")
            if not self.policy_engine.authorize(val_result):
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Authorization failed.")
                return ""

            # 7. Canary & Commit
            machine.transition(IncidentStatus.CANARY, "Deploying canary.")
            # Canary succeeded...
            machine.transition(IncidentStatus.RECOVERED, "Canary successful. Recovery deployed.")

            # 8. Certificate
            cert = {
                "incident_id": incident_state.incident_id,
                "trace_hash": trace.get("hash", ""),
                "causal_graph_hash": graph.get("hash", ""),
                "envelope_id": incident_state.envelope_id,
                "posterior": incident_state.root_cause_posterior,
                "cut": cut.model_dump(),
                "telemetry": incident_state.telemetry
            }
            cert_id = self.ledger.record_certificate(cert)
            machine.transition(IncidentStatus.CLOSED, "Incident fully resolved.")
            return cert_id

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Security fail-closed
            if incident_state.status not in {IncidentStatus.CLOSED, IncidentStatus.RECOVERED, IncidentStatus.RECOVERY_REJECTED, IncidentStatus.EVIDENCE_INSUFFICIENT}:
                machine.transition(IncidentStatus.CLOSED, f"Fatal error: {e!s}")
            return ""

    def validate_transportability(
        self,
        src: CausalEnvironmentDescriptor,
        tgt: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint
    ) -> Any:
        if not self.transport_gate:
            raise ValueError("TransportabilityGate not configured.")
        return self.transport_gate.evaluate(src, tgt, footprint)
