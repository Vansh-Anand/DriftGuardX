from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import ResourceContext, ResourceMeasurement
from packages.ledger.src.crypto import DevelopmentSigner
from packages.replay.src.admission_receipt import (
    AdmissionReceiptV1,
    ReceiptStatus,
    ReplayAdmissionReceipt,
)


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


def test_legacy_name_is_canonical_v1_contract() -> None:
    receipt = _issue(ResourceContext(budget_usd=2.0))

    assert isinstance(receipt, AdmissionReceiptV1)
    assert receipt.schema_version == "1"
    assert receipt.receipt_id in receipt.canonical_payload.values()
    assert receipt.nonce


def test_canonical_bytes_are_stable_for_equivalent_utc_times() -> None:
    issued = datetime(2026, 9, 8, 10, 30, tzinfo=UTC)
    first = _issue(
        ResourceContext(budget_usd=2.0),
        issued_at=issued,
        expires_at=issued + timedelta(minutes=5),
    )
    second = _issue(
        ResourceContext(budget_usd=2.0),
        issued_at=issued,
        expires_at=issued + timedelta(minutes=5),
        receipt_id=first.receipt_id,
        nonce=first.nonce,
    )

    assert first.canonical_bytes == second.canonical_bytes
    assert first.binding_hash == second.binding_hash


def test_naive_receipt_times_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _issue(
            ResourceContext(budget_usd=2.0),
            issued_at=datetime(2026, 9, 8, 10, 30),
            expires_at=datetime(2026, 9, 8, 10, 35),
        )


def test_signed_receipt_verifies_and_tampering_fails() -> None:
    signer = DevelopmentSigner(key_id="admission-test-key")
    receipt = _issue(ResourceContext(budget_usd=2.0))

    receipt.sign(signer)

    assert receipt.verify_signature(signer.public_key_b64()) == (True, "ok")
    original_hash = receipt.binding_hash
    receipt.policy_hash = "tampered-policy"
    assert receipt.binding_hash != original_hash
    assert receipt.verify_signature(signer.public_key_b64())[0] is False


def test_strict_binding_does_not_coerce_types() -> None:
    receipt = _issue(ResourceContext(budget_usd=2.0))

    valid, reason = receipt.verify_binding(predicted_cost="1.0")

    assert not valid
    assert "predicted_cost" in reason
