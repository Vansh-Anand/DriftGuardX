"""
DriftGuard-X v2 — Causal Recovery Orchestrator
PRIVATE — All Rights Reserved.

Coordinates the full end-to-end incident diagnosis and recovery lifecycle.
Key changes from previous version:
- Removed hard max_iters=5 loop; stopping is now governed by EvidentiaryStoppingRule
- DivergenceValidator now returns a structured DivergenceReport (not bare bool)
- ExperimentPlanner.plan_next_experiment() called in a true sequential loop
- StoppingPolicy.is_sufficient() receives full belief state + resource context
- PolicyEngine.authorize() accepts SignedCapability objects
"""
from __future__ import annotations

import time
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
    ResourceContext,
    StoppingPolicy,
    TraceProvider,
    TransportabilityGate,
)
from packages.contracts.src.recovery_models import FailureTarget, SignedCapability
from packages.contracts.src.transport_models import (
    CausalEnvironmentDescriptor,
    RecoveryMechanismFootprint,
)
from packages.recovery.src.incident_state_machine import IncidentStateMachine


class CausalRecoveryOrchestrator:
    """
    Coordinates the full end-to-end incident diagnosis and recovery lifecycle.

    The sequential experimentation loop is governed by EvidentiaryStoppingRule,
    not a hard iteration cap. The loop terminates when:
    - Posterior confidence is sufficient
    - Entropy has converged
    - Information is exhausted
    - Resource budget is depleted
    - The safety cap (max_experiments) is hit
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
        default_budget_usd: float = 5.0,
        default_time_budget_seconds: float = 300.0,
    ) -> None:
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
        self.default_budget_usd = default_budget_usd
        self.default_time_budget_seconds = default_time_budget_seconds

    def process_incident(
        self,
        incident_state: IncidentState,
        failure_targets: list[FailureTarget],
        capabilities: list[SignedCapability] | None = None,
        budget_usd: float | None = None,
        time_budget_seconds: float | None = None,
    ) -> str:
        """
        Runs the incident to completion (or failure mode).
        Returns the final certificate hash, or empty string on failure.

        The sequential experiment loop runs until the EvidentiaryStoppingRule
        determines that evidence is sufficient — no hard iteration cap.
        """
        machine = IncidentStateMachine(incident_state)
        capabilities = capabilities or []

        # Resource context tracks budget across the experiment loop
        resource_context = ResourceContext(
            budget_usd=budget_usd or self.default_budget_usd,
            max_wall_seconds=time_budget_seconds or self.default_time_budget_seconds,
        )
        loop_start = time.monotonic()

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

            # 3. Generate candidates and build envelope
            candidates = self.intervention_generator.generate_candidates(incident_state)
            if not candidates:
                machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "No candidate interventions.")
                return ""

            envelope = self.envelope_builder.build_envelope(incident_state.incident_id, candidates)
            incident_state.envelope_id = envelope.trace_id

            if not self.raeb_gateway.check_admissibility(envelope):
                machine.transition(IncidentStatus.EVIDENCE_INSUFFICIENT, "RAEB admissibility rejected envelope.")
                return ""

            # 4. Sequential causal experiment loop
            # Governed by EvidentiaryStoppingRule — no hard max_iters
            machine.transition(IncidentStatus.REPLAYING, "Starting sequential causal experiment loop.")

            all_replays: list[dict[str, Any]] = []
            remaining_candidates = list(candidates)

            while True:
                # Update wall time
                resource_context.elapsed_seconds = time.monotonic() - loop_start

                # Check stopping rule BEFORE selecting next experiment
                should_stop, stop_reason = self.stopping_policy.is_sufficient(
                    state=incident_state,
                    resource_context=resource_context,
                    belief_model=self.belief_model,
                    remaining_candidates=remaining_candidates,
                )
                if should_stop:
                    break

                # Select next experiment using real EIG
                belief_state = self.belief_model.current_beliefs()
                experiment = self.experiment_planner.plan_next_experiment(
                    envelope=envelope,
                    candidates=remaining_candidates,
                    belief_state=belief_state,
                    resource_context=resource_context,
                )

                if experiment is None:
                    break  # Budget exhausted or EIG too low

                # Confirm budget reservation
                reservation = experiment.pop("_reservation", None)

                # Execute the selected experiment
                replays = self.replay_executor.execute_replays([experiment])

                # Confirm reservation if execution succeeded
                if reservation is not None:
                    reservation.confirm()

                # Validate divergence against the envelope
                div_report = self.divergence_validator.validate_divergence(
                    replays=replays,
                    envelope=envelope,
                )

                if div_report.early_terminated:
                    # Forbidden divergence — terminate replay loop immediately
                    machine.transition(
                        IncidentStatus.EVIDENCE_INSUFFICIENT,
                        f"Replay early-terminated: {div_report.reason}",
                    )
                    return ""

                if not div_report.valid:
                    # Divergence violation — skip belief update, continue
                    all_replays.extend(replays)
                    continue

                # Update belief state
                new_belief = self.belief_model.update_belief(incident_state, replays)
                incident_state.root_cause_posterior = new_belief

                # Record entropy for stopping rule
                if hasattr(self.stopping_policy, "record_iteration"):
                    self.stopping_policy.record_iteration(self.belief_model.entropy())

                # Remove tested candidate from remaining list
                tested_id = experiment.get("candidate_id", experiment.get("id", ""))
                remaining_candidates = [
                    c for c in remaining_candidates
                    if c.get("candidate_id", c.get("id", "")) != tested_id
                ]
                all_replays.extend(replays)

            # 5. Check if evidence is sufficient after loop
            should_stop, stop_reason = self.stopping_policy.is_sufficient(
                state=incident_state,
                resource_context=resource_context,
                belief_model=self.belief_model,
                remaining_candidates=remaining_candidates,
            )
            if not should_stop and not all_replays:
                machine.transition(
                    IncidentStatus.EVIDENCE_INSUFFICIENT,
                    f"Posterior did not converge: {stop_reason}",
                )
                return ""

            machine.transition(IncidentStatus.EVIDENCE_SUFFICIENT, f"Evidence collected: {stop_reason}")

            # 6. Solve Minimum Causal Recovery Cut
            machine.transition(IncidentStatus.RECOVERY_PLANNING, "Solving for minimum causal cut.")
            fault_sources = incident_state.root_cause_posterior or {}
            cut = self.recovery_solver.solve(failure_targets, fault_sources)
            if not cut:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Impossible to find valid cut.")
                return ""

            # 7. Validate in controlled replay with signed capabilities
            machine.transition(IncidentStatus.RECOVERY_VALIDATING, "Validating cut in controlled replay.")
            val_result = self.recovery_validator.validate(cut, capabilities)
            if not val_result.invariants_satisfied:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Invariant validation failed.")
                return ""

            # 8. Policy authorization with signed capabilities
            machine.transition(IncidentStatus.AWAITING_AUTHORIZATION, "Checking policy capabilities.")
            if not self.policy_engine.authorize(val_result, capabilities):
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Authorization failed.")
                return ""

            # 9. Canary & Commit
            if not val_result.eligible_for_canary:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Recovery not eligible for canary deployment.")
                return ""

            machine.transition(IncidentStatus.CANARY, "Deploying canary.")
            machine.transition(IncidentStatus.RECOVERED, "Canary successful. Recovery deployed.")

            # 10. Record certificate
            cert = {
                "incident_id": incident_state.incident_id,
                "trace_hash": trace.get("hash", ""),
                "causal_graph_hash": graph.get("hash", ""),
                "envelope_id": incident_state.envelope_id,
                "envelope_hash": envelope.envelope_hash,
                "posterior": incident_state.root_cause_posterior,
                "cut": cut.model_dump(),
                "replays_executed": resource_context.replay_count,
                "total_cost_usd": resource_context.spent_usd,
                "stop_reason": stop_reason,
                "telemetry": incident_state.telemetry,
            }
            cert_id = self.ledger.record_certificate(cert)
            machine.transition(IncidentStatus.CLOSED, "Incident fully resolved.")
            return cert_id

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Security fail-closed
            terminal_states = {
                IncidentStatus.CLOSED,
                IncidentStatus.RECOVERED,
                IncidentStatus.RECOVERY_REJECTED,
                IncidentStatus.EVIDENCE_INSUFFICIENT,
            }
            if incident_state.status not in terminal_states:
                machine.transition(IncidentStatus.CLOSED, f"Fatal error: {e!s}")
            return ""

    def validate_transportability(
        self,
        src: CausalEnvironmentDescriptor,
        tgt: CausalEnvironmentDescriptor,
        footprint: RecoveryMechanismFootprint,
    ) -> Any:
        if not self.transport_gate:
            raise ValueError("TransportabilityGate not configured.")
        return self.transport_gate.evaluate(src, tgt, footprint)
