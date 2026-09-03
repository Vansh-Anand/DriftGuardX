"""
DriftGuard-X v2 — Recovery Executor Framework
PRIVATE — All Rights Reserved.

Executors are the ONLY path to side-effecting recovery actions.
Every executor:
  1. Validates the proposal params against the ACTION_REGISTRY allowlist.
  2. Checks the idempotency key to prevent duplicate execution.
  3. Verifies the live component version matches expected_version_id (optimistic lock).
  4. Creates a RollbackCapsule BEFORE mutating state.
  5. Executes only through an allowlisted adapter method.
  6. Returns an ExecutionResult with success, outcome, and capsule_id.

Development/sandbox mode (default):
  - All adapters operate on in-memory local fixtures.
  - No real service calls, no external network requests.
  - Behaviour is deterministic and reproducible.

Production adapters require DRIFTGUARDX_ENV=production env var.
They are injected via the executor factory and are NOT imported by default.
"""

from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.recovery.src.actions import (
    ACTION_REGISTRY,
    ExecutionMode,
    RecoveryActionType,
    RecoveryProposal,
)
from packages.recovery.src.capsule import (
    CapsuleRegistry,
    CompatibilityConstraint,
    RollbackCapsule,
)

# ─── Result ───────────────────────────────────────────────────────────────────


@dataclass
class ExecutionResult:
    proposal_id: str
    success: bool
    outcome_description: str
    capsule_id: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    side_effects: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ─── Errors ───────────────────────────────────────────────────────────────────


class IdempotencyConflictError(ValueError):
    """Raised when the idempotency key has already been used."""

    pass


class StaleVersionError(ValueError):
    """Raised when the live component version doesn't match expected."""

    pass


class ActionNotAllowedError(PermissionError):
    """Raised when the action type is not in the registry allowlist."""

    pass


class ParamValidationError(ValueError):
    """Raised when required params are missing or unknown params are present."""

    pass


# ─── Abstract Executor ────────────────────────────────────────────────────────


class RecoveryExecutor(abc.ABC):
    """
    Abstract base for all recovery executors.

    Subclasses implement _prepare_capsule() and _apply() only.
    All guard logic (idempotency, optimistic lock, param validation) is
    enforced by execute() before calling _apply().
    """

    def __init__(self, capsule_registry: CapsuleRegistry):
        self._capsule_reg = capsule_registry
        self._used_idempotency_keys: set[str] = set()
        # Local fixture: mock component version state
        self._live_versions: dict[str, str] = {}

    def register_live_version(self, component_id: str, version_id: str) -> None:
        """Register a component's current version (used in tests and dev mode)."""
        self._live_versions[component_id] = version_id

    def execute(self, proposal: RecoveryProposal) -> ExecutionResult:
        """
        Main entry point. Enforces all pre-execution guards.
        """
        # ── Guard 1: Allowlist check ──────────────────────────────────────────
        if proposal.action_type not in ACTION_REGISTRY:
            raise ActionNotAllowedError(
                f"Action {proposal.action_type!r} is not in the executor allowlist."
            )

        # ── Guard 2: Param validation ─────────────────────────────────────────
        errors = proposal.validate_params()
        if errors:
            raise ParamValidationError(f"Param validation failed: {errors}")

        # ── Guard 3: Idempotency ──────────────────────────────────────────────
        idem_key = f"{proposal.proposal_id}:{proposal.idempotency_key}"
        if idem_key in self._used_idempotency_keys:
            raise IdempotencyConflictError(
                f"Idempotency key {proposal.idempotency_key!r} already used for proposal "
                f"{proposal.proposal_id!r}. Duplicate execution suppressed."
            )

        # ── Guard 4: Optimistic version lock ──────────────────────────────────
        if proposal.expected_version_id is not None:
            component_id = proposal.params.get("component_id")
            if component_id:
                live = self._live_versions.get(component_id)
                if live != proposal.expected_version_id:
                    raise StaleVersionError(
                        f"Stale state: component {component_id!r} expected version "
                        f"{proposal.expected_version_id!r}, found {live!r}. "
                        "Aborting to prevent incorrect recovery."
                    )

        # ── Guard 5: Dry-run short-circuit ────────────────────────────────────
        if proposal.execution_mode == ExecutionMode.DRY_RUN:
            return ExecutionResult(
                proposal_id=proposal.proposal_id,
                success=True,
                outcome_description=f"[DRY_RUN] Would execute {proposal.action_type.value}.",
                execution_mode=ExecutionMode.DRY_RUN,
            )

        # ── Prepare: snapshot current state + create capsule ──────────────────
        capsule = self._prepare_capsule(proposal)
        self._capsule_reg.store(capsule)

        # ── Execute ───────────────────────────────────────────────────────────
        result = self._apply(proposal, capsule)
        result.capsule_id = capsule.capsule_id
        result.execution_mode = proposal.execution_mode

        # ── Record idempotency key on success ─────────────────────────────────
        if result.success:
            self._used_idempotency_keys.add(idem_key)

        return result

    @abc.abstractmethod
    def _prepare_capsule(self, proposal: RecoveryProposal) -> RollbackCapsule:
        """Snapshot current state and build the rollback capsule."""
        ...

    @abc.abstractmethod
    def _apply(self, proposal: RecoveryProposal, capsule: RollbackCapsule) -> ExecutionResult:
        """Apply the recovery action. May not raise — return success=False on error."""
        ...

    def compensate(self, capsule: RollbackCapsule) -> ExecutionResult:
        """
        Execute the rollback described by the capsule.
        Returns ExecutionResult with success=True if compensation succeeded.
        """
        usable, reason = capsule.is_usable()
        if not usable:
            return ExecutionResult(
                proposal_id=capsule.proposal_id,
                success=False,
                outcome_description=f"Capsule unusable: {reason}",
                capsule_id=capsule.capsule_id,
                error=reason,
            )

        result = self._rollback(capsule)
        if result.success:
            capsule.seal_used()
        return result

    @abc.abstractmethod
    def _rollback(self, capsule: RollbackCapsule) -> ExecutionResult:
        """Apply the rollback described in the capsule."""
        ...


# ─── Local Dev Executor (Sandbox / Fixture-backed) ────────────────────────────


class LocalDevExecutor(RecoveryExecutor):
    """
    Fully in-memory, deterministic executor for development and tests.
    Never makes real service calls.
    Simulates each allowlisted action on local fixture state.
    """

    def __init__(self, capsule_registry: CapsuleRegistry):
        super().__init__(capsule_registry)
        # In-memory fixture state for each action type
        self._top_k_store: dict[str, int] = {}
        self._index_store: dict[str, str] = {}
        self._reranker_store: dict[str, str] = {}
        self._model_store: dict[str, str] = {}
        self._tools_disabled: set[str] = set()
        self._quarantined_ns: set[str] = set()
        self._prompt_versions: dict[str, str] = {}

    # ── Capsule preparation ───────────────────────────────────────────────────

    def _prepare_capsule(self, proposal: RecoveryProposal) -> RollbackCapsule:
        prev = self._snapshot_state(proposal)
        target = dict(proposal.params)

        component_id = proposal.params.get("component_id", "unknown")
        self._live_versions.get(component_id)

        constraints = []
        if proposal.expected_version_id and component_id != "unknown":
            constraints.append(
                CompatibilityConstraint(
                    component_id=component_id,
                    expected_version_id=proposal.expected_version_id,
                    description="Component must be at expected version for safe rollback.",
                )
            )

        return RollbackCapsule(
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type.value,
            tenant_id=proposal.tenant_id,
            component_id=component_id,
            previous_state=prev,
            target_state=target,
            artifact_hashes=(
                {component_id: hashlib.sha256(str(prev).encode()).hexdigest()[:16]} if prev else {}
            ),
            compatibility_constraints=constraints,
            rollback_params=prev,  # rollback = restore previous state
            verify_steps=["canary_replay", "metric_delta_check"],
            created_by=proposal.requester_id,
        )

    def _snapshot_state(self, proposal: RecoveryProposal) -> dict[str, Any]:
        """Capture current fixture state relevant to this action."""
        t = proposal.action_type
        params = proposal.params
        if t == RecoveryActionType.INCREASE_TOP_K:
            cid = params.get("component_id", "")
            return {"component_id": cid, "top_k": self._top_k_store.get(cid, 10)}
        if t == RecoveryActionType.RETRY_HYBRID_RETRIEVAL:
            cid = params.get("component_id", "")
            return {"component_id": cid, "strategy": "dense"}  # default
        if t == RecoveryActionType.SWITCH_STABLE_INDEX:
            cid = params.get("component_id", "")
            return {"component_id": cid, "index_id": self._index_store.get(cid, "index_v1")}
        if t == RecoveryActionType.RERANK:
            cid = params.get("component_id", "")
            return {"component_id": cid, "reranker_id": self._reranker_store.get(cid, "none")}
        if t == RecoveryActionType.ROUTE_STABLE_MODEL:
            cid = params.get("component_id", "")
            return {"component_id": cid, "model": self._model_store.get(cid, "gpt-4")}
        if t == RecoveryActionType.DISABLE_TEST_TOOL:
            tid = params.get("tool_id", "")
            return {"tool_id": tid, "disabled": tid in self._tools_disabled}
        if t == RecoveryActionType.QUARANTINE_MEMORY_NS:
            ns = params.get("namespace_id", "")
            return {"namespace_id": ns, "quarantined": ns in self._quarantined_ns}
        if t == RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION:
            pid = params.get("partition_id", "")
            # Assume not quarantined initially if not tracked, store handles reality
            from packages.memory.src.store import global_provenance_store

            is_quarantined = global_provenance_store._is_quarantined(pid)
            return {"partition_id": pid, "quarantined": is_quarantined}
        if t == RecoveryActionType.REVERT_PROMPT_VERSION:
            pid = params.get("prompt_id", "")
            return {"prompt_id": pid, "version_tag": self._prompt_versions.get(pid, "v1")}
        if t == RecoveryActionType.ROLLBACK_COMPONENT:
            cid = params.get("component_id", "")
            return {"component_id": cid, "version_id": self._live_versions.get(cid)}
        return {}

    # ── Action application ────────────────────────────────────────────────────

    def _apply(self, proposal: RecoveryProposal, capsule: RollbackCapsule) -> ExecutionResult:
        t = proposal.action_type
        params = proposal.params
        try:
            if t == RecoveryActionType.INCREASE_TOP_K:
                cid = params["component_id"]
                new_k = int(params["new_top_k"])
                max_k = int(params.get("max_allowed_top_k", 100))
                if new_k > max_k:
                    return ExecutionResult(
                        proposal_id=proposal.proposal_id,
                        success=False,
                        outcome_description=f"new_top_k={new_k} exceeds max={max_k}.",
                        error="top_k_exceeds_limit",
                    )
                self._top_k_store[cid] = new_k
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"top_k for {cid!r} set to {new_k}.",
                    side_effects={"top_k": new_k},
                )

            if t == RecoveryActionType.RETRY_HYBRID_RETRIEVAL:
                cid = params["component_id"]
                strategy = params["strategy"]
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Retrieval strategy for {cid!r} set to {strategy!r}.",
                    side_effects={"strategy": strategy},
                )

            if t == RecoveryActionType.SWITCH_STABLE_INDEX:
                cid = params["component_id"]
                idx = params["target_index_id"]
                self._index_store[cid] = idx
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Index for {cid!r} switched to {idx!r}.",
                    side_effects={"index_id": idx},
                )

            if t == RecoveryActionType.RERANK:
                cid = params["component_id"]
                rr = params["reranker_id"]
                self._reranker_store[cid] = rr
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Reranker for {cid!r} set to {rr!r}.",
                    side_effects={"reranker_id": rr},
                )

            if t == RecoveryActionType.ROUTE_STABLE_MODEL:
                cid = params["component_id"]
                alias = params["stable_model_alias"]
                self._model_store[cid] = alias
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Model for {cid!r} routed to {alias!r}.",
                    side_effects={"model": alias},
                )

            if t == RecoveryActionType.DISABLE_TEST_TOOL:
                tid = params["tool_id"]
                self._tools_disabled.add(tid)
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Tool {tid!r} disabled.",
                    side_effects={"tool_id": tid, "disabled": True},
                )

            if t == RecoveryActionType.QUARANTINE_MEMORY_NS:
                ns = params["namespace_id"]
                self._quarantined_ns.add(ns)
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Namespace {ns!r} quarantined (read-only).",
                    side_effects={"namespace_id": ns, "quarantined": True},
                )

            if t == RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION:
                pid = params["partition_id"]
                import os
                import uuid
                from datetime import datetime, timedelta

                from packages.contracts.src.recovery_models import SignedCapability
                from packages.memory.src.auth import AccessContext
                from packages.memory.src.capabilities import CapabilityVerifier
                from packages.memory.src.store import global_provenance_store

                secret = os.environ.get("DGX_CAPABILITY_SECRET")
                verifier = CapabilityVerifier(secret.encode("utf-8") if secret else None)
                cap = SignedCapability(
                    capability_id=uuid.uuid4().hex,
                    requester_id="executor",
                    tenant_id=proposal.tenant_id,
                    action="QUARANTINE",
                    resource=pid,
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                cap = verifier.sign(cap)
                ctx = AccessContext(
                    requester_id="executor",
                    tenant_id=proposal.tenant_id,
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    capabilities=[cap],
                )
                global_provenance_store.quarantine_partition(
                    pid, context=ctx, reason=f"Quarantined by proposal {proposal.proposal_id}"
                )
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Provenance partition {pid!r} quarantined globally.",
                    side_effects={"partition_id": pid, "quarantined": True},
                )

            if t == RecoveryActionType.REVERT_PROMPT_VERSION:
                pid = params["prompt_id"]
                vtag = params["target_version_tag"]
                self._prompt_versions[pid] = vtag
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Prompt {pid!r} reverted to {vtag!r}.",
                    side_effects={"prompt_id": pid, "version_tag": vtag},
                )

            if t == RecoveryActionType.ROLLBACK_COMPONENT:
                cid = params["component_id"]
                target_vid = params["target_version_id"]
                self._live_versions[cid] = target_vid
                return ExecutionResult(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outcome_description=f"Component {cid!r} rolled back to {target_vid!r}.",
                    side_effects={"component_id": cid, "version_id": target_vid},
                )

        except (KeyError, ValueError) as exc:
            return ExecutionResult(
                proposal_id=proposal.proposal_id,
                success=False,
                outcome_description=f"Execution error: {exc}",
                error=str(exc),
            )

        return ExecutionResult(
            proposal_id=proposal.proposal_id,
            success=False,
            outcome_description=f"Action {t!r} not implemented in LocalDevExecutor.",
            error="not_implemented",
        )

    def _rollback(self, capsule: RollbackCapsule) -> ExecutionResult:
        """Restore previous state from capsule snapshot."""
        prev = capsule.previous_state
        t = capsule.action_type

        try:
            if t == RecoveryActionType.INCREASE_TOP_K.value:
                self._top_k_store[prev["component_id"]] = prev["top_k"]
            elif t == RecoveryActionType.SWITCH_STABLE_INDEX.value:
                self._index_store[prev["component_id"]] = prev["index_id"]
            elif t == RecoveryActionType.RERANK.value:
                self._reranker_store[prev["component_id"]] = prev["reranker_id"]
            elif t == RecoveryActionType.ROUTE_STABLE_MODEL.value:
                self._model_store[prev["component_id"]] = prev["model"]
            elif t == RecoveryActionType.DISABLE_TEST_TOOL.value:
                if not prev.get("disabled", False):
                    self._tools_disabled.discard(prev["tool_id"])
            elif t == RecoveryActionType.QUARANTINE_MEMORY_NS.value:
                if not prev.get("quarantined", False):
                    self._quarantined_ns.discard(prev["namespace_id"])
            elif t == RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION.value:
                if not prev.get("quarantined", False):
                    import os
                    import uuid
                    from datetime import datetime, timedelta

                    from packages.contracts.src.recovery_models import SignedCapability
                    from packages.memory.src.auth import AccessContext
                    from packages.memory.src.capabilities import CapabilityVerifier
                    from packages.memory.src.store import global_provenance_store

                    secret = os.environ.get("DGX_CAPABILITY_SECRET")
                    verifier = CapabilityVerifier(secret.encode("utf-8") if secret else None)
                    cap = SignedCapability(
                        capability_id=uuid.uuid4().hex,
                        requester_id="executor",
                        tenant_id="system",
                        action="UNQUARANTINE",
                        resource=prev["partition_id"],
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    )
                    cap = verifier.sign(cap)
                    ctx = AccessContext(
                        requester_id="executor",
                        tenant_id="system",
                        expires_at=datetime.now(UTC) + timedelta(minutes=5),
                        capabilities=[cap],
                    )
                    global_provenance_store.unquarantine_partition(
                        prev["partition_id"], context=ctx
                    )
            elif t == RecoveryActionType.REVERT_PROMPT_VERSION.value:
                self._prompt_versions[prev["prompt_id"]] = prev["version_tag"]
            elif t == RecoveryActionType.ROLLBACK_COMPONENT.value:
                self._live_versions[prev["component_id"]] = prev["version_id"]
            else:
                return ExecutionResult(
                    proposal_id=capsule.proposal_id,
                    success=False,
                    outcome_description=f"No rollback handler for action {t!r}.",
                    error="no_rollback_handler",
                )
        except (KeyError, TypeError) as exc:
            return ExecutionResult(
                proposal_id=capsule.proposal_id,
                success=False,
                outcome_description=f"Rollback failed: {exc}",
                error=str(exc),
            )

        return ExecutionResult(
            proposal_id=capsule.proposal_id,
            success=True,
            outcome_description=f"Rolled back {t!r} using capsule {capsule.capsule_id!r}.",
            capsule_id=capsule.capsule_id,
        )
