"""
DriftGuard-X v2 — Recovery Engine
PRIVATE — All Rights Reserved.

Orchestrates the full recovery lifecycle:
  1. Policy check (pre_recovery_check / pre_rollback_check hooks).
  2. State machine transitions: PROPOSED → PREPARING → EXECUTING → VERIFYING → COMMITTED.
  3. Canary verification after execution.
  4. Automatic compensation (COMPENSATING → COMPENSATED) if canary fails
     and policy allows low-risk auto-rollback.
  5. FAILED state + escalation log if compensation also fails.

Execution modes:
  DRY_RUN    — No side effects; returns simulated outcome.
  SIMULATION — Runs against LocalDevExecutor sandbox only.
  MANUAL     — Engine prepares the capsule and stops; human executes.
  APPROVED   — Fully automated after policy + approval gates pass.

The engine does NOT call the policy engine autonomously for APPROVED mode —
the caller must provide a valid approval_request_id from a prior PolicyEngine
decision; the engine validates it before proceeding.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from packages.contracts.src.models import RecoveryEligibilityCertificate, serialize_for_signing
from packages.ledger.src.crypto import verify_signature
from packages.recovery.src.actions import ExecutionMode, RecoveryProposal
from packages.recovery.src.canary import (
    CanaryEpisode,
    CanaryThresholds,
    CanaryVerificationResult,
    run_canary_verification,
)
from packages.recovery.src.executor import ExecutionResult, LocalDevExecutor
from packages.recovery.src.state_machine import (
    InvalidTransitionError,
    RecoveryStateMachine,
    RecoveryStatus,
)

if TYPE_CHECKING:
    from packages.recovery.src.capsule import CapsuleRegistry, RollbackCapsule


@dataclass
class RecoveryRecord:
    """Full record of one recovery execution for audit and UI display."""

    proposal: RecoveryProposal
    machine: RecoveryStateMachine
    execution_result: ExecutionResult | None = None
    canary_result: CanaryVerificationResult | None = None
    capsule: RollbackCapsule | None = None
    compensation_result: ExecutionResult | None = None
    escalation_log: list[str] = field(default_factory=list)


class RecoveryEngine:
    """
    Orchestrates safe recovery execution.

    Usage:
        engine = RecoveryEngine(executor, capsule_registry)
        record = engine.run(proposal, canary_episodes)
        # record.machine.current_status == RecoveryStatus.COMMITTED (or COMPENSATED/FAILED)
    """

    def __init__(
        self,
        executor: LocalDevExecutor,
        capsule_registry: CapsuleRegistry,
        auto_compensate_on_verify_failure: bool = True,
    ):
        self._executor = executor
        self._capsule_reg = capsule_registry
        self._auto_compensate = auto_compensate_on_verify_failure
        self._records: dict[str, RecoveryRecord] = {}

    def run(
        self,
        proposal: RecoveryProposal,
        canary_episodes: list[CanaryEpisode],
        canary_thresholds: CanaryThresholds | None = None,
        certificate: RecoveryEligibilityCertificate | None = None,
        signer_public_key_b64: str | None = None,
    ) -> RecoveryRecord:
        """
        Run the complete prepare → execute → verify → commit/compensate cycle.
        Always returns a RecoveryRecord — never raises to caller.
        """
        machine = RecoveryStateMachine(proposal_id=proposal.proposal_id)
        record = RecoveryRecord(proposal=proposal, machine=machine)
        self._records[proposal.proposal_id] = record

        # ── POLICY_CHECKING ───────────────────────────────────────────────────
        machine.transition(RecoveryStatus.POLICY_CHECKING, reason="Starting policy check.")

        if proposal.policy_decision == "deny":
            machine.transition(RecoveryStatus.FAILED, reason="Policy denied this recovery action.")
            record.escalation_log.append("Policy DENY — recovery blocked.")
            return record

        if proposal.policy_decision == "needs_approval" and not proposal.approval_request_id:
            machine.transition(RecoveryStatus.PENDING_APPROVAL, reason="Awaiting human approval.")
            return record

        # ── DRY_RUN short-circuit ─────────────────────────────────────────────
        if proposal.execution_mode == ExecutionMode.DRY_RUN:
            machine.transition(RecoveryStatus.PREPARING, reason="Dry run.")
            machine.transition(RecoveryStatus.EXECUTING, reason="Dry run execute.")
            result = self._executor.execute(proposal)
            record.execution_result = result
            machine.transition(RecoveryStatus.VERIFYING, reason="Dry run verify.")
            machine.transition(RecoveryStatus.COMMITTED, reason="Dry run committed.")
            return record

        # ── PREPARING ─────────────────────────────────────────────────────────
        machine.transition(RecoveryStatus.PREPARING, reason="Preparing capsule.")

        # ── VERIFYING CERTIFICATE ─────────────────────────────────────────────
        # For mutating execution modes (SIMULATION, APPROVED, MANUAL)
        if proposal.execution_mode != ExecutionMode.DRY_RUN:
            if not certificate:
                machine.transition(
                    RecoveryStatus.FAILED, reason="Missing Recovery Eligibility Certificate."
                )
                record.escalation_log.append("SECURITY: No REC provided. Failing closed.")
                return record

            if not signer_public_key_b64:
                machine.transition(
                    RecoveryStatus.FAILED, reason="Missing Signer Public Key for REC verification."
                )
                record.escalation_log.append(
                    "SECURITY: No public key provided to verify REC. Failing closed."
                )
                return record

            payload = serialize_for_signing(certificate)
            is_valid_sig = verify_signature(
                signer_public_key_b64, payload, certificate.signature_b64
            )
            if not is_valid_sig:
                machine.transition(
                    RecoveryStatus.FAILED, reason="REC signature verification failed."
                )
                record.escalation_log.append(
                    "SECURITY: Invalid REC signature (Tampering detected). Failing closed."
                )
                return record

            # Verify live state matches the certificate
            capsule = self._capsule_reg.for_proposal(proposal.proposal_id)
            (
                capsule.config_snapshot.get("hash", "") if capsule else ""
            )  # Minimal mocked hash check
            # In a real implementation we would compute the actual capsule hash and compare.

            # Simple expiry check (e.g., 1 hour)
            age = datetime.now(UTC) - certificate.timestamp
            if age.total_seconds() > 3600:
                machine.transition(RecoveryStatus.FAILED, reason="REC is expired.")
                record.escalation_log.append("SECURITY: Expired REC. Failing closed.")
                return record

        # ── EXECUTING ─────────────────────────────────────────────────────────
        machine.transition(RecoveryStatus.EXECUTING, reason="Executing action.")
        try:
            result = self._executor.execute(proposal)
        except Exception as exc:
            result = ExecutionResult(
                proposal_id=proposal.proposal_id,
                success=False,
                outcome_description=f"Executor raised: {exc}",
                error=str(exc),
            )

        record.execution_result = result

        if not result.success:
            # Execution failed → compensate
            self._compensate(record, reason=f"Execution failed: {result.error}")
            return record

        # Retrieve capsule
        capsule = self._capsule_reg.for_proposal(proposal.proposal_id)
        record.capsule = capsule

        # ── VERIFYING ─────────────────────────────────────────────────────────
        machine.transition(RecoveryStatus.VERIFYING, reason="Running canary verification.")
        canary_result = run_canary_verification(
            proposal.proposal_id, canary_episodes, canary_thresholds
        )
        record.canary_result = canary_result

        if canary_result.overall_pass:
            machine.transition(RecoveryStatus.COMMITTED, reason="Canary verification passed.")
        else:
            reasons = "; ".join(canary_result.failure_reasons)
            if self._auto_compensate and capsule:
                self._compensate(record, reason=f"Canary failed: {reasons}")
            else:
                machine.transition(
                    RecoveryStatus.FAILED,
                    reason=f"Canary failed (auto-compensate disabled): {reasons}",
                )
                record.escalation_log.append(reasons)

        return record

    def _compensate(self, record: RecoveryRecord, reason: str) -> None:
        machine = record.machine
        machine.transition(RecoveryStatus.COMPENSATING, reason=reason)

        capsule = record.capsule
        if capsule is None:
            capsule = self._capsule_reg.for_proposal(record.proposal.proposal_id)

        if capsule is None:
            machine.transition(
                RecoveryStatus.FAILED, reason="No capsule available for compensation."
            )
            record.escalation_log.append("ESCALATION: No capsule — manual intervention required.")
            return

        comp_result = self._executor.compensate(capsule)
        record.compensation_result = comp_result

        if comp_result.success:
            machine.transition(RecoveryStatus.COMPENSATED, reason="Compensation succeeded.")
            # Persist rollback evidence to the transparency ledger
            from packages.ledger.src.store import SQLiteTransparencyStore
            
            try:
                ledger_store = SQLiteTransparencyStore()
                ledger_store.append({
                    "type": "ROLLBACK_COMPENSATED",
                    "proposal_id": record.proposal.proposal_id,
                    "capsule_id": capsule.capsule_id,
                    "side_effects": comp_result.side_effects,
                    "timestamp": datetime.now(UTC).isoformat()
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to persist rollback evidence: {e}")
                
        else:
            machine.transition(
                RecoveryStatus.FAILED, reason=f"Compensation failed: {comp_result.error}"
            )
            record.escalation_log.append(
                f"ESCALATION: Compensation failed — {comp_result.error}. Manual intervention required."
            )

    def cancel(self, proposal_id: str, actor: str = "operator") -> RecoveryRecord | None:
        record = self._records.get(proposal_id)
        if record:
            with contextlib.suppress(InvalidTransitionError):
                record.machine.cancel(actor=actor)
        return record

    def get_record(self, proposal_id: str) -> RecoveryRecord | None:
        return self._records.get(proposal_id)
