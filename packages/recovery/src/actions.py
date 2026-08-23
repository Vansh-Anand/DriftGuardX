"""
DriftGuard-X v2 — Recovery Action Schemas
PRIVATE — All Rights Reserved.

Defines the complete allowlist of safe recovery actions.
Every action has an explicit type, allowlisted parameter schema, risk tier,
reversibility flag, and idempotency key strategy.

The allowlist principle:
  - Executors ONLY call methods listed in ACTION_REGISTRY.
  - No free-form shell commands, arbitrary SQL, or dynamic imports.
  - Development/sandbox mode has its own executor that operates on local
    fixtures only; production adapters require explicit env-var opt-in.
"""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# ─── Enums ────────────────────────────────────────────────────────────────────

class RecoveryActionType(str, enum.Enum):
    # ── Retriever recovery ─────────────────────────────────────────────────────
    INCREASE_TOP_K         = "increase_top_k"          # LOW-RISK: widen retrieval window
    RETRY_HYBRID_RETRIEVAL = "retry_hybrid_retrieval"  # LOW-RISK: switch retrieval strategy
    SWITCH_STABLE_INDEX    = "switch_stable_index"     # MEDIUM: point to a known-good index

    # ── Ranking / model ────────────────────────────────────────────────────────
    RERANK                 = "rerank"                  # LOW-RISK: add/replace reranker
    ROUTE_STABLE_MODEL     = "route_stable_model"      # MEDIUM: redirect to stable model alias

    # ── Memory / tool safety ───────────────────────────────────────────────────
    DISABLE_TEST_TOOL      = "disable_test_tool"       # MEDIUM: disable flagged tool
    QUARANTINE_MEMORY_NS   = "quarantine_memory_ns"    # MEDIUM: read-only fence on namespace
    QUARANTINE_PROVENANCE_PARTITION = "quarantine_provenance_partition" # MEDIUM: adversarial provenance quarantine (Update 3)

    # ── Prompt / config ────────────────────────────────────────────────────────
    REVERT_PROMPT_VERSION  = "revert_prompt_version"   # MEDIUM: restore previous prompt tag
    ROLLBACK_COMPONENT     = "rollback_component"      # HIGH: rollback a component version


class ExecutionMode(str, enum.Enum):
    DRY_RUN    = "dry_run"     # no side effects; simulate and return expected outcome
    SIMULATION = "simulation"  # local fixture sandbox only
    MANUAL     = "manual"      # system prepares, human executes
    APPROVED   = "approved"    # automated after policy + approval gates pass


class RecoveryStatus(str, enum.Enum):
    PROPOSED        = "proposed"
    POLICY_CHECKING = "policy_checking"
    PENDING_APPROVAL= "pending_approval"
    PREPARING       = "preparing"
    EXECUTING       = "executing"
    VERIFYING       = "verifying"
    COMMITTED       = "committed"
    COMPENSATING    = "compensating"
    COMPENSATED     = "compensated"
    FAILED          = "failed"
    CANCELLED       = "cancelled"


# ─── Action Definition ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ActionDefinition:
    """
    Immutable definition of an allowlisted recovery action.
    All actions must be present in ACTION_REGISTRY to be executed.
    """
    action_type: RecoveryActionType
    risk_tier: str                       # low | medium | high | critical
    is_reversible: bool                  # whether a rollback capsule is mandatory
    required_params: tuple[str, ...]     # param names that must be present
    optional_params: tuple[str, ...]     # param names that may be present
    description: str


ACTION_REGISTRY: dict[RecoveryActionType, ActionDefinition] = {
    RecoveryActionType.INCREASE_TOP_K: ActionDefinition(
        action_type=RecoveryActionType.INCREASE_TOP_K,
        risk_tier="low",
        is_reversible=True,
        required_params=("component_id", "new_top_k"),
        optional_params=("max_allowed_top_k",),
        description="Increase retrieval top-k within configured limits.",
    ),
    RecoveryActionType.RETRY_HYBRID_RETRIEVAL: ActionDefinition(
        action_type=RecoveryActionType.RETRY_HYBRID_RETRIEVAL,
        risk_tier="low",
        is_reversible=True,
        required_params=("component_id", "strategy"),
        optional_params=("alpha",),
        description="Switch to hybrid (dense+sparse) retrieval strategy.",
    ),
    RecoveryActionType.SWITCH_STABLE_INDEX: ActionDefinition(
        action_type=RecoveryActionType.SWITCH_STABLE_INDEX,
        risk_tier="medium",
        is_reversible=True,
        required_params=("component_id", "target_index_id"),
        optional_params=("verify_checksum",),
        description="Point retriever to a known-good stable index.",
    ),
    RecoveryActionType.RERANK: ActionDefinition(
        action_type=RecoveryActionType.RERANK,
        risk_tier="low",
        is_reversible=True,
        required_params=("component_id", "reranker_id"),
        optional_params=("top_n",),
        description="Add or replace the reranker with a specified model.",
    ),
    RecoveryActionType.ROUTE_STABLE_MODEL: ActionDefinition(
        action_type=RecoveryActionType.ROUTE_STABLE_MODEL,
        risk_tier="medium",
        is_reversible=True,
        required_params=("component_id", "stable_model_alias"),
        optional_params=("max_tokens",),
        description="Route generation to a stable model alias.",
    ),
    RecoveryActionType.DISABLE_TEST_TOOL: ActionDefinition(
        action_type=RecoveryActionType.DISABLE_TEST_TOOL,
        risk_tier="medium",
        is_reversible=True,
        required_params=("tool_id",),
        optional_params=("reason",),
        description="Disable a flagged tool in the sandbox tool registry.",
    ),
    RecoveryActionType.QUARANTINE_MEMORY_NS: ActionDefinition(
        action_type=RecoveryActionType.QUARANTINE_MEMORY_NS,
        risk_tier="medium",
        is_reversible=True,
        required_params=("namespace_id", "tenant_id"),
        optional_params=("ttl_hours",),
        description="Place a test memory namespace into read-only quarantine.",
    ),
    RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION: ActionDefinition(
        action_type=RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION,
        risk_tier="medium",
        is_reversible=True,
        required_params=("partition_id",),
        optional_params=("document_set", "tool_route", "preserve_challenge_examples"),
        description="Quarantine a specific provenance partition (e.g., specific document set or agent route) without global rollback.",
    ),
    RecoveryActionType.REVERT_PROMPT_VERSION: ActionDefinition(
        action_type=RecoveryActionType.REVERT_PROMPT_VERSION,
        risk_tier="medium",
        is_reversible=True,
        required_params=("prompt_id", "target_version_tag"),
        optional_params=("reason",),
        description="Restore a prompt to a previous stable version tag.",
    ),
    RecoveryActionType.ROLLBACK_COMPONENT: ActionDefinition(
        action_type=RecoveryActionType.ROLLBACK_COMPONENT,
        risk_tier="high",
        is_reversible=True,
        required_params=("component_id", "target_version_id", "expected_current_version_id"),
        optional_params=("dry_run",),
        description="Roll back a component to a previous stable version (requires approval).",
    ),
}


# ─── Recovery Proposal ────────────────────────────────────────────────────────

@dataclass
class RecoveryProposal:
    """
    A proposed recovery action for a specific run/diagnosis.

    All fields required before execution:
      - idempotency_key: caller-supplied; prevents duplicate execution.
      - expected_version_id: optimistic lock — executor checks this before mutating.
      - certificate_id: diagnosis certificate that authorized this recovery.
      - policy_decision: set by PolicyEngine before PREPARE.
    """
    action_type: RecoveryActionType
    tenant_id: str
    node_id: str
    run_id: str
    diagnosis_id: str
    requester_id: str
    params: dict[str, Any]
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN

    # Pre-execution guards
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))
    expected_version_id: str | None = None   # optimistic lock
    certificate_id: str | None = None         # cert must be CERTIFIED or UNCERTIFIED+reviewed

    # Set by system
    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    status: RecoveryStatus = RecoveryStatus.PROPOSED
    policy_decision: str | None = None        # "allow" | "deny" | "needs_approval"
    approval_request_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def param_hash(self) -> str:
        """Deterministic content hash of params for idempotency checking."""
        payload = json.dumps(
            {"action": self.action_type, "params": self.params},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def validate_params(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        defn = ACTION_REGISTRY.get(self.action_type)
        if defn is None:
            return [f"Unknown action type: {self.action_type!r}"]
        errors = []
        for required in defn.required_params:
            if required not in self.params:
                errors.append(f"Missing required param: {required!r}")
        all_known = set(defn.required_params) | set(defn.optional_params)
        for key in self.params:
            if key not in all_known:
                errors.append(f"Unknown param: {key!r} (not in allowlist)")
        return errors
