"""
DriftGuard-X v2 — Recovery State Machine
PRIVATE — All Rights Reserved.

Implements saga-style execution with explicit states and compensations.

State transitions:
  PROPOSED
    → POLICY_CHECKING
    → PENDING_APPROVAL  (if policy requires it)
    → PREPARING         (snapshot current state, create capsule)
    → EXECUTING         (apply the action via allowlisted adapter)
    → VERIFYING         (canary replay + metric checks)
    → COMMITTED         (terminal success)
    → COMPENSATING      (triggered on VERIFY failure or timeout)
    → COMPENSATED       (terminal: rolled back successfully)
    → FAILED            (terminal: compensation also failed; escalate)
    → CANCELLED         (operator cancelled before EXECUTING)

Partial failure contract:
  - EXECUTING → failure → COMPENSATING (not FAILED)
  - COMPENSATING → failure → FAILED (manual intervention required)
  - A result of COMMITTED is ONLY set after VERIFYING passes.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, List, Optional, Any


class RecoveryStatus(str, enum.Enum):
    PROPOSED         = "proposed"
    POLICY_CHECKING  = "policy_checking"
    PENDING_APPROVAL = "pending_approval"
    PREPARING        = "preparing"
    EXECUTING        = "executing"
    VERIFYING        = "verifying"
    COMMITTED        = "committed"
    COMPENSATING     = "compensating"
    COMPENSATED      = "compensated"
    FAILED           = "failed"
    CANCELLED        = "cancelled"


# Terminal states — no further transitions permitted
TERMINAL_STATES = frozenset({
    RecoveryStatus.COMMITTED,
    RecoveryStatus.COMPENSATED,
    RecoveryStatus.FAILED,
    RecoveryStatus.CANCELLED,
})

# Allowed transitions (from → set of allowed tos)
ALLOWED_TRANSITIONS: Dict[RecoveryStatus, frozenset] = {
    RecoveryStatus.PROPOSED:         frozenset({RecoveryStatus.POLICY_CHECKING, RecoveryStatus.CANCELLED}),
    RecoveryStatus.POLICY_CHECKING:  frozenset({RecoveryStatus.PENDING_APPROVAL, RecoveryStatus.PREPARING, RecoveryStatus.FAILED, RecoveryStatus.CANCELLED}),
    RecoveryStatus.PENDING_APPROVAL: frozenset({RecoveryStatus.PREPARING, RecoveryStatus.CANCELLED}),
    RecoveryStatus.PREPARING:        frozenset({RecoveryStatus.EXECUTING, RecoveryStatus.FAILED, RecoveryStatus.CANCELLED}),
    RecoveryStatus.EXECUTING:        frozenset({RecoveryStatus.VERIFYING, RecoveryStatus.COMPENSATING}),
    RecoveryStatus.VERIFYING:        frozenset({RecoveryStatus.COMMITTED, RecoveryStatus.COMPENSATING}),
    RecoveryStatus.COMPENSATING:     frozenset({RecoveryStatus.COMPENSATED, RecoveryStatus.FAILED}),
    RecoveryStatus.COMMITTED:        frozenset(),
    RecoveryStatus.COMPENSATED:      frozenset(),
    RecoveryStatus.FAILED:           frozenset(),
    RecoveryStatus.CANCELLED:        frozenset(),
}


class InvalidTransitionError(ValueError):
    pass


@dataclass
class StateEvent:
    """Immutable log entry for one state transition."""
    from_status: RecoveryStatus
    to_status: RecoveryStatus
    actor: str
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryStateMachine:
    """
    Tracks one recovery execution from PROPOSED to a terminal state.

    All transitions are validated. Terminal states are immutable.
    The event log is append-only and never truncated.
    """
    proposal_id: str
    current_status: RecoveryStatus = RecoveryStatus.PROPOSED
    capsule_id: Optional[str] = None
    event_log: List[StateEvent] = field(default_factory=list)
    timeout_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    retry_count: int = 0
    max_retries: int = 2
    escalated: bool = False

    def transition(
        self,
        to_status: RecoveryStatus,
        actor: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Move to a new status. Raises InvalidTransitionError on illegal moves.
        Raises TimeoutError if the machine has exceeded its timeout.
        """
        if self.current_status in TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Cannot transition from terminal state {self.current_status}."
            )
        if datetime.now(timezone.utc) > self.timeout_at:
            # Force compensate on timeout
            self._force_timeout()
            return

        allowed = ALLOWED_TRANSITIONS.get(self.current_status, frozenset())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"Transition {self.current_status} → {to_status} is not allowed. "
                f"Allowed: {sorted(s.value for s in allowed)}"
            )

        event = StateEvent(
            from_status=self.current_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
            metadata=metadata or {},
        )
        self.event_log.append(event)
        self.current_status = to_status

    def cancel(self, actor: str = "operator", reason: str = "Operator cancelled.") -> None:
        """Cancel if not yet in terminal or executing state."""
        if self.current_status in TERMINAL_STATES:
            raise InvalidTransitionError("Cannot cancel a terminal recovery.")
        if self.current_status == RecoveryStatus.EXECUTING:
            raise InvalidTransitionError(
                "Cannot cancel while executing; trigger COMPENSATING instead."
            )
        self.transition(RecoveryStatus.CANCELLED, actor=actor, reason=reason)

    def _force_timeout(self) -> None:
        """Internal: escalate to FAILED via COMPENSATING on timeout."""
        if self.current_status not in TERMINAL_STATES:
            event = StateEvent(
                from_status=self.current_status,
                to_status=RecoveryStatus.COMPENSATING,
                actor="system",
                reason="Timeout exceeded; forcing compensation.",
            )
            self.event_log.append(event)
            self.current_status = RecoveryStatus.COMPENSATING
            self.escalated = True

    def should_retry(self) -> bool:
        return (
            self.current_status == RecoveryStatus.EXECUTING
            and self.retry_count < self.max_retries
        )

    def record_retry(self) -> None:
        self.retry_count += 1

    def is_terminal(self) -> bool:
        return self.current_status in TERMINAL_STATES
