"""
DriftGuard-X v2 — Rollback Capsule
PRIVATE — All Rights Reserved.

A RollbackCapsule is a self-contained record that enables safe reversal of
a recovery action. It is mandatory for any action where is_reversible=True.

Contents:
  - previous_state:  snapshot of the component config BEFORE the action.
  - target_state:    state that was applied (or intended to be applied).
  - artifact hashes: SHA-256 of any configuration/artifact files involved.
  - compatibility:   list of constraints that must hold for rollback to be safe.
  - exec_command:    abstract execution command (NOT a shell string — a typed
                     RecoveryProposal-compatible descriptor).
  - verify_steps:    ordered list of verification step IDs to run post-rollback.
  - expires_at:      after this time, the capsule is considered stale and must
                     not be used for automatic rollback.

A capsule is IMMUTABLE once sealed. Reverting using a sealed capsule is
itself a policy-gated operation (risk_tier = action's tier, or at least MEDIUM).
"""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4


class CapsuleStatus(str, enum.Enum):
    ACTIVE   = "active"    # usable for rollback
    USED     = "used"      # already consumed (prevents reuse)
    EXPIRED  = "expired"   # past expires_at
    VOIDED   = "voided"    # explicitly voided by operator (cannot be reused)


@dataclass
class CompatibilityConstraint:
    """A condition that must be true for a rollback to be safe."""
    component_id: str
    expected_version_id: str
    description: str


@dataclass
class RollbackCapsule:
    """
    Immutable rollback capsule.

    created_by / proposal_id link the capsule to the recovery action that
    produced it so it can be surfaced in the audit trail.
    """
    # Identity
    capsule_id: str = field(default_factory=lambda: str(uuid4()))
    proposal_id: str = ""       # recovery proposal that produced this capsule
    action_type: str = ""       # RecoveryActionType value
    tenant_id: str = ""
    component_id: str = ""

    # State snapshots
    previous_state: Dict[str, Any] = field(default_factory=dict)
    target_state: Dict[str, Any] = field(default_factory=dict)

    # Artifact hashes (SHA-256; verify before rollback)
    artifact_hashes: Dict[str, str] = field(default_factory=dict)

    # Compatibility checks — all must pass before rollback proceeds
    compatibility_constraints: List[CompatibilityConstraint] = field(default_factory=list)

    # Abstract rollback command (typed, not a shell string)
    rollback_params: Dict[str, Any] = field(default_factory=dict)

    # Verification steps to run after rollback completes
    verify_steps: List[str] = field(default_factory=list)

    # Lifecycle
    status: CapsuleStatus = CapsuleStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=72)
    )
    used_at: Optional[datetime] = None
    created_by: str = "system"

    # Integrity seal (computed on creation, verified before use)
    _integrity_hash: str = field(default="", init=False, repr=False)

    def __post_init__(self):
        self._integrity_hash = self._compute_integrity()

    def _compute_integrity(self) -> str:
        payload = json.dumps({
            "capsule_id": self.capsule_id,
            "proposal_id": self.proposal_id,
            "action_type": self.action_type,
            "tenant_id": self.tenant_id,
            "component_id": self.component_id,
            "previous_state": self.previous_state,
            "rollback_params": self.rollback_params,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def integrity_hash(self) -> str:
        return self._integrity_hash

    def verify_integrity(self) -> bool:
        """Returns True if the capsule has not been tampered with."""
        return self._compute_integrity() == self._integrity_hash

    def is_usable(self) -> tuple[bool, str]:
        """Returns (usable, reason). Capsule must be ACTIVE and not expired."""
        now = datetime.now(timezone.utc)
        if self.status == CapsuleStatus.USED:
            return False, "Capsule already consumed."
        if self.status == CapsuleStatus.VOIDED:
            return False, "Capsule has been voided by an operator."
        if self.status == CapsuleStatus.EXPIRED or now > self.expires_at:
            return False, f"Capsule expired at {self.expires_at.isoformat()}."
        if not self.verify_integrity():
            return False, "Capsule integrity check failed — possible tampering."
        return True, "ok"

    def check_compatibility(
        self, live_versions: Dict[str, str]
    ) -> List[str]:
        """
        Check all compatibility constraints against live component versions.
        Returns list of constraint violation descriptions (empty = compatible).
        """
        violations = []
        for c in self.compatibility_constraints:
            live = live_versions.get(c.component_id)
            if live != c.expected_version_id:
                violations.append(
                    f"Component {c.component_id!r}: expected version "
                    f"{c.expected_version_id!r}, found {live!r}. "
                    f"Constraint: {c.description}"
                )
        return violations

    def seal_used(self) -> None:
        """Mark capsule as consumed (prevents reuse)."""
        self.status = CapsuleStatus.USED
        self.used_at = datetime.now(timezone.utc)


# ─── Capsule Registry ─────────────────────────────────────────────────────────

class CapsuleRegistry:
    """In-memory capsule store. Production: backed by DB table."""

    def __init__(self):
        self._capsules: dict[str, RollbackCapsule] = {}

    def store(self, capsule: RollbackCapsule) -> None:
        self._capsules[capsule.capsule_id] = capsule

    def get(self, capsule_id: str) -> Optional[RollbackCapsule]:
        cap = self._capsules.get(capsule_id)
        if cap and cap.status == CapsuleStatus.ACTIVE:
            now = datetime.now(timezone.utc)
            if now > cap.expires_at:
                cap.status = CapsuleStatus.EXPIRED
        return cap

    def for_proposal(self, proposal_id: str) -> Optional[RollbackCapsule]:
        for cap in self._capsules.values():
            if cap.proposal_id == proposal_id:
                return cap
        return None

    def void(self, capsule_id: str) -> None:
        cap = self._capsules.get(capsule_id)
        if cap:
            cap.status = CapsuleStatus.VOIDED
