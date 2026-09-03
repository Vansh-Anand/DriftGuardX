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
from typing import TYPE_CHECKING, Any

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
    ResourceMeasurement,
    StoppingPolicy,
    TraceProvider,
    TransportabilityGate,
)
from packages.recovery.src.incident_state_machine import IncidentStateMachine
from packages.replay.src.stopping_rule import StoppingOutcome

if TYPE_CHECKING:
    from packages.contracts.src.recovery_models import FailureTarget
    from packages.contracts.src.transport_models import (
        CausalEnvironmentDescriptor,
        RecoveryMechanismFootprint,
    )
    from packages.memory.src.auth import AccessContext


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
        access_context: AccessContext | None = None,
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
        capabilities = access_context.capabilities if access_context else []

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
                machine.transition(
                    IncidentStatus.EVIDENCE_INSUFFICIENT, "No candidate interventions."
                )
                return ""

            envelope = self.envelope_builder.build_envelope(incident_state.incident_id, candidates)
            incident_state.envelope_id = envelope.trace_id

            if not self.raeb_gateway.check_admissibility(envelope):
                machine.transition(
                    IncidentStatus.EVIDENCE_INSUFFICIENT, "RAEB admissibility rejected envelope."
                )
                return ""

            # 4. Sequential causal experiment loop
            # Governed by EvidentiaryStoppingRule — no hard max_iters
            machine.transition(
                IncidentStatus.REPLAYING, "Starting sequential causal experiment loop."
            )

            all_replays: list[dict[str, Any]] = []
            remaining_candidates = list(candidates)
            valid_evidence_count = 0

            while True:
                # Update wall time
                resource_context.elapsed_seconds = time.monotonic() - loop_start

                # Check stopping rule BEFORE selecting next experiment
                should_stop, stop_outcome, stop_reason = self.stopping_policy.is_sufficient(
                    state=incident_state,
                    resource_context=resource_context,
                    belief_model=self.belief_model,
                    remaining_candidates=remaining_candidates,
                )
                # A posterior or mock policy cannot authorize recovery without
                # at least one replay that passed divergence validation.
                if should_stop and (
                    stop_outcome != StoppingOutcome.CONFIRMED or valid_evidence_count > 0
                ):
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
                    # If planner returns None but stopping rule didn't trigger, we exhausted admissible experiments.
                    # Re-evaluate stopping rule to get the final outcome.
                    should_stop, stop_outcome, stop_reason = self.stopping_policy.is_sufficient(
                        state=incident_state,
                        resource_context=resource_context,
                        belief_model=self.belief_model,
                        remaining_candidates=[],  # Force empty to reflect exhaustion
                    )
                    if valid_evidence_count == 0:
                        stop_outcome = StoppingOutcome.NO_ADMISSIBLE_EXPERIMENT
                        stop_reason = "No replay passed divergence validation."
                    break

                # Confirm budget reservation
                reservation = experiment.pop("_reservation", None)

                # Execute the selected experiment
                execution_started = time.monotonic()
                try:
                    replays = self.replay_executor.execute_replays([experiment])
                except Exception:
                    if reservation is not None:
                        reservation.release()
                    raise

                # Reconcile the reservation with measured execution time and
                # an executor-reported cost when available.
                if reservation is not None:
                    actual_cost = sum(
                        float(replay.get("actual_cost_usd", 0.0)) for replay in replays
                    )
                    if actual_cost <= 0.0:
                        actual_cost = reservation.estimate.cost_usd
                    reservation.commit(
                        ResourceMeasurement(
                            cost_usd=actual_cost,
                            replay_count=len(replays),
                            wall_seconds=time.monotonic() - execution_started,
                        )
                    )

                tested_id = experiment.get("candidate_id", experiment.get("id", ""))
                remaining_candidates = [
                    candidate
                    for candidate in remaining_candidates
                    if candidate.get("candidate_id", candidate.get("id", "")) != tested_id
                ]

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
                valid_evidence_count += len(replays)
                incident_state.root_cause_posterior = new_belief

                # Record entropy for stopping rule
                if hasattr(self.stopping_policy, "record_iteration"):
                    self.stopping_policy.record_iteration(self.belief_model.entropy())

                all_replays.extend(replays)

            # Preserve explicit telemetry as requested
            beliefs = self.belief_model.current_beliefs()
            top_posterior = 0.0
            margin = 0.0
            if beliefs:
                sorted_vals = sorted(beliefs.values(), reverse=True)
                top_posterior = sorted_vals[0]
                if len(sorted_vals) >= 2:
                    margin = sorted_vals[0] - sorted_vals[1]

            valid_replays = [r for r in all_replays if r.get("status") == "completed"]
            invalid_replays = [r for r in all_replays if r.get("status") != "completed"]

            incident_state.telemetry.update(
                {
                    "stop_outcome": stop_outcome.value,
                    "stop_reason": stop_reason,
                    "top_posterior": top_posterior,
                    "posterior_margin": margin,
                    "entropy": self.belief_model.entropy(),
                    "replay_count": resource_context.replay_count,
                    "valid_replay_count": len(valid_replays),
                    "invalid_replay_count": len(invalid_replays),
                    "resource_state": {
                        "budget_used_usd": resource_context.spent_usd,
                        "elapsed_seconds": resource_context.elapsed_seconds,
                    },
                }
            )

            if stop_outcome == StoppingOutcome.CONFIRMED:
                machine.transition(
                    IncidentStatus.EVIDENCE_SUFFICIENT, f"Evidence confirmed: {stop_reason}"
                )
            else:
                machine.transition(
                    IncidentStatus.EVIDENCE_INSUFFICIENT,
                    f"Evidence insufficient. Outcome: {stop_outcome.value} - {stop_reason}",
                )
                return ""

            # 6. Solve Minimum Causal Recovery Cut
            machine.transition(IncidentStatus.RECOVERY_PLANNING, "Solving for minimum causal cut.")
            fault_sources = incident_state.root_cause_posterior or {}
            cut = self.recovery_solver.solve(failure_targets, fault_sources)
            if not cut:
                machine.transition(
                    IncidentStatus.RECOVERY_REJECTED, "Impossible to find valid cut."
                )
                return ""

            # 7. Validate in controlled replay with signed capabilities
            machine.transition(
                IncidentStatus.RECOVERY_VALIDATING, "Validating cut in controlled replay."
            )
            if access_context is None or not access_context.is_valid():
                machine.transition(
                    IncidentStatus.RECOVERY_REJECTED,
                    "Missing or expired authenticated recovery access context.",
                )
                return ""
            val_result = self.recovery_validator.validate_cut(
                cut=cut,
                invariants=envelope.invariants,
                trace_id=envelope.trace_id,
                original_spans=trace.get("spans", []),
                access_context=access_context,
                exogenous_variables=envelope.exogenous_variables,
            )
            if not val_result.invariants_satisfied:
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Invariant validation failed.")
                return ""

            # 8. Policy authorization with signed capabilities
            machine.transition(
                IncidentStatus.AWAITING_AUTHORIZATION, "Checking policy capabilities."
            )
            if not self.policy_engine.authorize(val_result, capabilities):
                machine.transition(IncidentStatus.RECOVERY_REJECTED, "Authorization failed.")
                return ""

            # 9. Canary & Commit
            if not val_result.eligible_for_canary:
                machine.transition(
                    IncidentStatus.RECOVERY_REJECTED, "Recovery not eligible for canary deployment."
                )
                return ""

            machine.transition(IncidentStatus.CANARY, "Deploying canary.")
            
            # We do not have a real canary deployment mechanism yet.
            # We must explicitly fail or halt rather than fabricating success.
            # No fake quarantine confirmation or simulated successful recovery.
            if incident_state.envelope_id: # placeholder check
                machine.transition(
                    IncidentStatus.RECOVERY_REJECTED, 
                    "Real canary deployments are currently blocked pending production support. Refusing to fabricate recovery success."
                )
                return ""
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
