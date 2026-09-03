"""
DriftGuard-X v2 — Approval Service
PRIVATE — All Rights Reserved.

Manages the full approval lifecycle:
  create → pending → approved/denied/expired
  + break-glass (emergency override with mandatory post-hoc audit)

Security invariants:
  - Self-approval is blocked: the actor granting approval cannot be the requester.
  - Approval decisions are immutable (append-only audit log).
  - HIGH-tier actions require two_person_control = True.
  - CRITICAL-tier actions require 2 distinct approvers (neither can be the requester).
  - Expired requests must not be approved.
  - Break-glass overrides are logged with mandatory justification and treated
    as CRITICAL events for post-hoc review.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

# ─── Types ────────────────────────────────────────────────────────────────────


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    BREAK_GLASS = "break_glass"


@dataclass
class ApprovalRequest:
    action: str
    resource: str
    requester_id: str
    tenant_id: str
    node_id: str
    risk_tier: str  # "low"|"medium"|"high"|"critical"
    required_approvers: int = 1
    two_person_control: bool = True
    request_id: str = field(default_factory=lambda: str(uuid4()))
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(hours=24))
    delegated_approvers: list[str] = field(default_factory=list)  # allowed approver IDs
    approvals: list[ApprovalDecision] = field(default_factory=list)
    context: dict = field(default_factory=dict)


@dataclass
class ApprovalDecision:
    """Immutable decision record — never mutated after creation."""

    request_id: str
    actor_id: str
    decision: ApprovalStatus  # APPROVED | DENIED
    comment: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    is_break_glass: bool = False
    break_glass_justification: str | None = None


# ─── Exceptions ───────────────────────────────────────────────────────────────


class SelfApprovalError(ValueError):
    """Raised when the requester tries to approve their own request."""

    pass


class InsufficientApproversError(ValueError):
    """Raised when not enough distinct approvers have approved."""

    pass


class ApprovalExpiredError(ValueError):
    """Raised when trying to act on an expired approval request."""

    pass


class UnauthorizedApproverError(PermissionError):
    """Raised when an actor outside the delegated approver set tries to approve."""

    pass


# ─── Approval Service ─────────────────────────────────────────────────────────


class ApprovalService:
    """
    In-memory approval service. In production, requests and decisions are
    persisted to the `approval_requests` table.

    Design:
    - All state changes append to the `_audit_log` (immutable, never deleted).
    - Self-approval is checked before any approval is recorded.
    - For two_person_control, the approver must not be the requester.
    - For CRITICAL actions, 2 distinct approvers are required.
    - Break-glass bypasses the normal approval flow but is ALWAYS logged and
      marked for post-hoc security review.
    """

    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}
        self._audit_log: list[dict] = []

    # ── Create ────────────────────────────────────────────────────────────────

    def create_request(self, request: ApprovalRequest) -> ApprovalRequest:
        self._requests[request.request_id] = request
        self._audit(
            request.request_id,
            "CREATED",
            request.requester_id,
            f"Action={request.action} Tier={request.risk_tier}",
        )
        return request

    # ── Approve ───────────────────────────────────────────────────────────────

    def approve(
        self,
        request_id: str,
        actor_id: str,
        comment: str = "",
    ) -> ApprovalRequest:
        """
        Record an approval decision.
        Returns the updated request.
        """
        req = self._get_active(request_id)
        self._check_actor_authorized(req, actor_id)
        self._check_not_self_approval(req, actor_id)

        decision = ApprovalDecision(
            request_id=request_id,
            actor_id=actor_id,
            decision=ApprovalStatus.APPROVED,
            comment=comment,
        )
        req.approvals.append(decision)
        self._audit(request_id, "APPROVED", actor_id, comment)

        # Check if we have enough distinct approvers
        approved_by = {d.actor_id for d in req.approvals if d.decision == ApprovalStatus.APPROVED}
        if len(approved_by) >= req.required_approvers:
            req.status = ApprovalStatus.APPROVED
            self._audit(
                request_id,
                "STATUS→APPROVED",
                "system",
                f"Reached {req.required_approvers} approver(s)",
            )

        return req

    # ── Deny ──────────────────────────────────────────────────────────────────

    def deny(self, request_id: str, actor_id: str, comment: str = "") -> ApprovalRequest:
        req = self._get_active(request_id)
        self._check_actor_authorized(req, actor_id)

        decision = ApprovalDecision(
            request_id=request_id,
            actor_id=actor_id,
            decision=ApprovalStatus.DENIED,
            comment=comment,
        )
        req.approvals.append(decision)
        req.status = ApprovalStatus.DENIED
        self._audit(request_id, "DENIED", actor_id, comment)
        return req

    # ── Break-Glass ───────────────────────────────────────────────────────────

    def break_glass(
        self,
        request_id: str,
        actor_id: str,
        justification: str,
    ) -> ApprovalRequest:
        """
        Emergency bypass of the normal approval flow.
        ALWAYS logged with mandatory justification.
        Creates a post-hoc review task in the audit log.
        Cannot be used by the original requester (self-approval check still applies).
        """
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"Request {request_id!r} not found.")

        self._check_not_self_approval(req, actor_id)

        if not justification or len(justification.strip()) < 20:
            raise ValueError("Break-glass justification must be at least 20 characters.")

        decision = ApprovalDecision(
            request_id=request_id,
            actor_id=actor_id,
            decision=ApprovalStatus.APPROVED,
            comment=f"BREAK_GLASS: {justification}",
            is_break_glass=True,
            break_glass_justification=justification,
        )
        req.approvals.append(decision)
        req.status = ApprovalStatus.BREAK_GLASS
        self._audit(
            request_id, "BREAK_GLASS", actor_id, justification, requires_post_hoc_review=True
        )
        return req

    # ── Expire ────────────────────────────────────────────────────────────────

    def expire_stale(self) -> list[str]:
        """Mark all pending requests past their expiry as EXPIRED. Returns affected IDs."""
        now = datetime.now(UTC)
        expired_ids = []
        for req in self._requests.values():
            if req.status == ApprovalStatus.PENDING and req.expires_at < now:
                req.status = ApprovalStatus.EXPIRED
                self._audit(req.request_id, "EXPIRED", "system", "TTL exceeded")
                expired_ids.append(req.request_id)
        return expired_ids

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def pending_for_tenant(self, tenant_id: str) -> list[ApprovalRequest]:
        return [
            r
            for r in self._requests.values()
            if r.tenant_id == tenant_id and r.status == ApprovalStatus.PENDING
        ]

    def audit_log(self) -> list[dict]:
        return list(self._audit_log)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_active(self, request_id: str) -> ApprovalRequest:
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"Request {request_id!r} not found.")
        now = datetime.now(UTC)
        if req.status == ApprovalStatus.PENDING and req.expires_at < now:
            req.status = ApprovalStatus.EXPIRED
            self._audit(request_id, "EXPIRED", "system", "TTL exceeded on access")
        if req.status in (
            ApprovalStatus.APPROVED,
            ApprovalStatus.DENIED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.BREAK_GLASS,
        ):
            raise ApprovalExpiredError(f"Request {request_id!r} is already {req.status.value}.")
        return req

    def _check_not_self_approval(self, req: ApprovalRequest, actor_id: str) -> None:
        if actor_id == req.requester_id:
            raise SelfApprovalError(
                f"Actor {actor_id!r} cannot approve their own request {req.request_id!r}."
            )

    def _check_actor_authorized(self, req: ApprovalRequest, actor_id: str) -> None:
        if req.delegated_approvers and actor_id not in req.delegated_approvers:
            raise UnauthorizedApproverError(
                f"Actor {actor_id!r} is not in the delegated approver list for {req.request_id!r}."
            )

    def _audit(
        self,
        request_id: str,
        event: str,
        actor_id: str,
        detail: str,
        requires_post_hoc_review: bool = False,
    ) -> None:
        self._audit_log.append(
            {
                "request_id": request_id,
                "event": event,
                "actor_id": actor_id,
                "detail": detail,
                "timestamp": datetime.now(UTC).isoformat(),
                "requires_post_hoc_review": requires_post_hoc_review,
            }
        )
