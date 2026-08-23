"""
DriftGuard-X v2 — Incident State Machine
PRIVATE — All Rights Reserved.
"""

from packages.contracts.src.incident_models import IncidentState, IncidentStatus

TERMINAL_STATES = frozenset({
    IncidentStatus.CLOSED,
})

ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.OBSERVING: frozenset({IncidentStatus.FAILURE_DETECTED, IncidentStatus.CLOSED}),
    IncidentStatus.FAILURE_DETECTED: frozenset({IncidentStatus.DIAGNOSING, IncidentStatus.CLOSED}),
    IncidentStatus.DIAGNOSING: frozenset({IncidentStatus.REPLAYING, IncidentStatus.EVIDENCE_INSUFFICIENT, IncidentStatus.CLOSED}),
    IncidentStatus.REPLAYING: frozenset({IncidentStatus.REPLAYING, IncidentStatus.EVIDENCE_SUFFICIENT, IncidentStatus.EVIDENCE_INSUFFICIENT, IncidentStatus.CLOSED}),
    IncidentStatus.EVIDENCE_SUFFICIENT: frozenset({IncidentStatus.RECOVERY_PLANNING, IncidentStatus.CLOSED}),
    IncidentStatus.EVIDENCE_INSUFFICIENT: frozenset({IncidentStatus.CLOSED}), # Fail closed if no evidence
    IncidentStatus.RECOVERY_PLANNING: frozenset({IncidentStatus.RECOVERY_VALIDATING, IncidentStatus.RECOVERY_REJECTED, IncidentStatus.CLOSED}),
    IncidentStatus.RECOVERY_VALIDATING: frozenset({IncidentStatus.AWAITING_AUTHORIZATION, IncidentStatus.RECOVERY_REJECTED, IncidentStatus.CLOSED}),
    IncidentStatus.AWAITING_AUTHORIZATION: frozenset({IncidentStatus.CANARY, IncidentStatus.RECOVERY_REJECTED, IncidentStatus.CLOSED}),
    IncidentStatus.CANARY: frozenset({IncidentStatus.RECOVERED, IncidentStatus.RECOVERY_REJECTED, IncidentStatus.CLOSED}),
    IncidentStatus.RECOVERED: frozenset({IncidentStatus.CLOSED}),
    IncidentStatus.RECOVERY_REJECTED: frozenset({IncidentStatus.CLOSED}),
    IncidentStatus.CLOSED: frozenset(),
}


class IncidentStateMachine:
    """Manages state transitions for the overall incident lifecycle."""

    def __init__(self, state: IncidentState):
        self.state = state

    def transition(self, to_status: IncidentStatus, reason: str = "") -> None:
        if self.state.status in TERMINAL_STATES:
            raise ValueError(f"Cannot transition from terminal state {self.state.status}")

        allowed = ALLOWED_TRANSITIONS.get(self.state.status, frozenset())
        if to_status not in allowed:
            raise ValueError(f"Invalid transition from {self.state.status} to {to_status}")

        self.state.status = to_status
        # Log to telemetry
        if "transition_log" not in self.state.telemetry:
            self.state.telemetry["transition_log"] = []
        self.state.telemetry["transition_log"].append({
            "from": self.state.status.value,
            "to": to_status.value,
            "reason": reason
        })
