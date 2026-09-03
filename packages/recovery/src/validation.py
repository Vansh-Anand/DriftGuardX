"""
DriftGuard-X v2 — Recovery Validation
PRIVATE — All Rights Reserved.

Real recovery validation pipeline:
1. Verify signed SignedCapability objects (not bare strings)
2. Build a full ReplayEquivalenceEnvelope with the cut's actions as intervened variables
3. Activate ExogenousStateController to freeze all external state
4. Execute the recovery replay through SandboxedWorker
5. Run DynamicCausalDivergenceValidator on original vs replay state
6. Evaluate all RecoveryInvariant objects against measured replay metrics
7. Only set eligible_for_canary=True when all of the above pass
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from packages.contracts.src.evidence import RecoveryEvidenceKind
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut,
    RecoveryInvariant,
    RecoveryValidationResult,
    ReplayContext,
    ReplayEquivalenceEnvelope,
    SandboxOutcome,
)
from packages.memory.src.capabilities import CapabilityVerifier
from packages.recovery.src.replay_executor import SyntheticRecoveryReplayExecutor
from packages.replay.src.divergence_validator import (
    DynamicCausalDivergenceValidator,
)

if TYPE_CHECKING:
    from packages.contracts.src.interfaces import RecoveryReplayExecutor
    from packages.memory.src.auth import AccessContext


class RecoveryValidator:
    """
    Validates a CausalRecoveryCut by executing it in a controlled replay
    and verifying all invariants against real measured metrics.
    """

    def __init__(
        self,
        verifier: CapabilityVerifier | None = None,
        divergence_validator: DynamicCausalDivergenceValidator | None = None,
        executor: RecoveryReplayExecutor | None = None,
    ) -> None:
        self.verifier = verifier or CapabilityVerifier()
        self.divergence_validator = divergence_validator or DynamicCausalDivergenceValidator()
        self.executor = executor or SyntheticRecoveryReplayExecutor()

    def validate_cut(
        self,
        cut: CausalRecoveryCut,
        invariants: list[RecoveryInvariant],
        trace_id: str,
        original_spans: list[dict[str, Any]] | None = None,
        access_context: AccessContext | None = None,
        exogenous_variables: dict[str, Any] | None = None,
        provided_capabilities: list[Any] | None = None,
    ) -> RecoveryValidationResult:
        """
        Full validation pipeline:
        1. Verify signed capabilities
        2. Build envelope
        3. Verify envelope integrity
        4. Run controlled replay (sandbox + exogenous controller)
        5. Run divergence validation
        6. Check invariants against measured metrics
        7. Determine canary eligibility
        """
        if access_context is None and provided_capabilities is None:
            return RecoveryValidationResult(
                recovery_cut=cut,
                failure_resolved=False,
                invariants=invariants,
                invariants_satisfied=False,
                divergence_report={"security": "No execution context provided."},
                residual_risk=1.0,
                eligible_for_canary=False,
                reason="Unauthorized recovery action — access context missing.",
            )

        effective_capabilities = (
            access_context.capabilities
            if access_context is not None
            else provided_capabilities or []
        )
        provided_ids = {
            cap.capability_id for cap in effective_capabilities if hasattr(cap, "capability_id")
        }

        original_spans = original_spans or []
        divergences: dict[str, Any] = {}
        invariants_satisfied = True
        failure_resolved = True
        reason = "Validation passed."

        # --- 1 & 2. Verify all signed capabilities and check requirements ---
        for action in cut.selected_actions:
            if action.required_capability is not None:
                cap = action.required_capability
                if cap.capability_id not in provided_ids:
                    return RecoveryValidationResult(
                        recovery_cut=cut,
                        failure_resolved=False,
                        invariants=invariants,
                        invariants_satisfied=False,
                        divergence_report={
                            "security": f"Missing required capability: {cap.capability_id} for action {action.action_id}"
                        },
                        residual_risk=1.0,
                        eligible_for_canary=False,
                        reason="Unauthorized recovery action — required signed capability not provided in context.",
                    )
                if access_context is None:
                    return RecoveryValidationResult(
                        recovery_cut=cut,
                        failure_resolved=False,
                        invariants=invariants,
                        invariants_satisfied=False,
                        divergence_report={
                            "security": "Signed capabilities require an access context."
                        },
                        residual_risk=1.0,
                        eligible_for_canary=False,
                        reason="Unauthorized recovery action — access context missing.",
                    )
                # Verify cryptographic integrity + contextual authorization
                if not self.verifier.verify(
                    cap,
                    access_context,
                    required_action=action.action_type,
                    required_resource=action.target_component,
                ):
                    return RecoveryValidationResult(
                        recovery_cut=cut,
                        failure_resolved=False,
                        invariants=invariants,
                        invariants_satisfied=False,
                        divergence_report={
                            "security": f"Invalid, expired, or unauthorized capability: {cap.capability_id}"
                        },
                        residual_risk=1.0,
                        eligible_for_canary=False,
                        reason="Unauthorized recovery action — capability verification failed.",
                    )

        # --- 3. Check residual failure paths ---
        if cut.residual_failure_paths:
            failure_resolved = False
            reason = "Residual failure-producing paths remain."

        # --- 4. Build ReplayEquivalenceEnvelope ---
        intervened = [a.target_component for a in cut.selected_actions]
        # Frozen: all non-intervened components from original spans
        frozen_vars: dict[str, str] = {}
        from packages.replay.src.divergence_validator import _stable_hash

        for span in original_spans:
            node_id = span.get("span_id", span.get("node_id", ""))
            component = span.get("component_type", "")
            if node_id and component not in intervened:
                frozen_vars[node_id] = _stable_hash(span.get("output", {}))

        envelope = ReplayEquivalenceEnvelope(
            trace_id=trace_id,
            recovery_cut=cut,
            invariants=invariants,
            frozen_variables=frozen_vars,
            intervened_variables=intervened,
            exogenous_variables=exogenous_variables or {},
            sandbox_config={"isolation_level": "strict"},
        )

        # Verify envelope integrity before execution
        if not envelope.verify_envelope_hash():
            return RecoveryValidationResult(
                recovery_cut=cut,
                failure_resolved=False,
                invariants=invariants,
                invariants_satisfied=False,
                divergence_report={
                    "security": "Envelope integrity check failed — possible tampering."
                },
                residual_risk=1.0,
                eligible_for_canary=False,
                reason="Envelope hash mismatch.",
            )

        # --- 5. Execute controlled replay ---
        import os

        if os.environ.get("DGX_MODE") == "production" and isinstance(
            self.executor, SyntheticRecoveryReplayExecutor
        ):
            return RecoveryValidationResult(
                recovery_cut=cut,
                failure_resolved=False,
                invariants=invariants,
                invariants_satisfied=False,
                divergence_report={"security": "Synthetic execution is forbidden in production."},
                residual_risk=1.0,
                eligible_for_canary=False,
                reason="Sandbox executor unavailable.",
            )

        context = ReplayContext(
            original_trace_id=trace_id,
            original_spans=original_spans,
        )
        try:
            result = self.executor.replay(None, cut, envelope, context)
            if result.outcome != SandboxOutcome.SUCCESS:
                outcome = str(result.outcome)
                return RecoveryValidationResult(
                    recovery_cut=cut,
                    failure_resolved=False,
                    invariants=invariants,
                    invariants_satisfied=False,
                    divergence_report={"error": f"Sandbox failed with outcome: {outcome}"},
                    residual_risk=1.0,
                    eligible_for_canary=False,
                    reason=f"Controlled replay failed: {outcome}",
                    evidence_kind=RecoveryEvidenceKind(result.evidence_kind),
                )

            replay_spans = result.new_spans
            measured_metrics = result.metrics
        except Exception as e:
            return RecoveryValidationResult(
                recovery_cut=cut,
                failure_resolved=False,
                invariants=invariants,
                invariants_satisfied=False,
                divergence_report={"error": str(e)},
                residual_risk=1.0,
                eligible_for_canary=False,
                reason=f"Controlled replay execution failed: {e}",
            )

        # --- 6. Divergence validation ---
        div_report = self.divergence_validator.validate_divergence(
            replays=[{"original_spans": original_spans, "replay_spans": replay_spans}],
            envelope=envelope,
        )
        if not div_report.valid:
            divergences["divergence"] = {
                "reason": div_report.reason,
                "frozen_violations": div_report.violated_frozen_nodes,
                "forbidden_violations": div_report.violated_forbidden_nodes,
                "per_node": div_report.per_node,
            }
            invariants_satisfied = False
            reason = f"Divergence validation failed: {div_report.reason}"

        # --- 7. Invariant check against measured metrics ---
        residual_risk = cut.regression_risk
        for inv in invariants:
            measured = measured_metrics.get(inv.metric, None)
            if measured is None:
                continue
            if measured > inv.baseline + inv.allowed_deviation:
                invariants_satisfied = False
                divergences[inv.invariant_id] = (
                    f"Metric '{inv.metric}' measured {measured:.4f} exceeds "
                    f"baseline {inv.baseline:.4f} + allowed {inv.allowed_deviation:.4f}."
                )
                reason = "Preservation invariant violated by measured replay metrics."

        eligible = (
            failure_resolved
            and invariants_satisfied
            and div_report.valid
            and result.evidence_kind != RecoveryEvidenceKind.SYNTHETIC_SIMULATION
        )
        if (
            result.evidence_kind == RecoveryEvidenceKind.SYNTHETIC_SIMULATION
            and reason == "Validation passed."
        ):
            reason = (
                "Synthetic simulation passed; controlled replay is required for canary eligibility."
            )

        return RecoveryValidationResult(
            recovery_cut=cut,
            failure_resolved=failure_resolved,
            invariants=invariants,
            invariants_satisfied=invariants_satisfied,
            divergence_report=divergences,
            residual_risk=residual_risk,
            eligible_for_canary=eligible,
            reason=reason,
            evidence_kind=RecoveryEvidenceKind(result.evidence_kind),
        )

    def validate(
        self,
        cut: CausalRecoveryCut,
        access_context: AccessContext | None = None,
    ) -> RecoveryValidationResult:
        """
        Orchestrator-compatible interface (minimal args).
        Uses default empty invariants and spans — the orchestrator should use
        validate_cut() directly for full validation.
        """
        return self.validate_cut(
            cut=cut,
            invariants=[],
            trace_id=cut.recovery_id,
            access_context=access_context,
        )
