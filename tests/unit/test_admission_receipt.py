from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import ResourceContext, ResourceMeasurement
from packages.replay.src.admission_receipt import ReceiptStatus, ReplayAdmissionReceipt


def _issue(context: ResourceContext, **overrides: object) -> ReplayAdmissionReceipt:
    values: dict[str, object] = {
        "resource_context": context,
        "tenant_id": "tenant-a",
        "manifest_hash": "manifest-hash",
        "trace_root_hash": "trace-hash",
        "intervention_hash": "intervention-hash",
        "current_version": "v1",
        "candidate_version": "v2",
        "policy_hash": "policy-hash",
        "predicted_cost": 1.0,
        "uncertainty_margin": 0.2,
        "rollback_reserve": 0.3,
        "evidence_ceiling": EvidenceClassification.REAL_CONTROLLED_EXPERIMENT,
        "capsule_hash": "capsule-hash",
        "issued_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
    }
    values.update(overrides)
    return ReplayAdmissionReceipt.issue(**values)


def test_receipt_reserves_bound_capacity_and_verifies() -> None:
    context = ResourceContext(budget_usd=2.0)
    receipt = _issue(context)

    assert context.reserved_usd == pytest.approx(1.5)
    assert receipt.verify_binding(manifest_hash="manifest-hash")[0]
    assert receipt.binding_hash


def test_binding_mismatch_refuses_without_consuming_reservation() -> None:
    context = ResourceContext(budget_usd=2.0)
    receipt = _issue(context)

    valid, reason = receipt.verify_binding(candidate_version="v3")

    assert not valid
    assert "candidate_version" in reason
    assert context.reserved_usd == pytest.approx(1.5)


def test_evidence_cannot_be_promoted() -> None:
    receipt = _issue(ResourceContext(budget_usd=2.0))

    valid, reason = receipt.verify_evidence(EvidenceClassification.PRODUCTION)

    assert not valid
    assert "ceiling" in reason


def test_release_is_idempotent_and_returns_capacity() -> None:
    context = ResourceContext(budget_usd=2.0)
    receipt = _issue(context)

    receipt.release()
    receipt.release()

    assert receipt.status == ReceiptStatus.RELEASED
    assert context.reserved_usd == pytest.approx(0.0)


def test_expired_receipt_is_voided_and_released() -> None:
    context = ResourceContext(budget_usd=2.0)
    receipt = _issue(
        context,
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    valid, reason = receipt.verify_binding()

    assert not valid
    assert "expired" in reason
    assert receipt.status == ReceiptStatus.VOIDED
    assert context.reserved_usd == pytest.approx(0.0)


def test_commit_reconciles_once() -> None:
    context = ResourceContext(budget_usd=2.0)
    receipt = _issue(context)

    receipt.commit(ResourceMeasurement(cost_usd=0.8, wall_seconds=2.0))

    assert receipt.status == ReceiptStatus.CONSUMED
    assert context.reserved_usd == pytest.approx(0.0)
    assert context.spent_usd == pytest.approx(0.8)
