from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import ResourceContext
from packages.recovery.src.actions import ExecutionMode, RecoveryActionType, RecoveryProposal
from packages.recovery.src.capsule import CapsuleRegistry
from packages.recovery.src.executor import LocalDevExecutor
from packages.replay.src.admission_receipt import ReplayAdmissionReceipt
from packages.replay.src.admission_store import AdmissionReceiptStore


@pytest.fixture
def store_path() -> Path:
    return Path(".local-runtime") / f"test-admission-{uuid4().hex}.sqlite3"


def _receipt(intervention_hash: str = "intervention-a") -> ReplayAdmissionReceipt:
    return ReplayAdmissionReceipt.issue(
        resource_context=ResourceContext(budget_usd=10.0),
        tenant_id="tenant-a",
        manifest_hash="manifest-a",
        trace_root_hash="trace-a",
        intervention_hash=intervention_hash,
        current_version="v1",
        candidate_version="v2",
        policy_hash="policy-a",
        predicted_cost=1.0,
        uncertainty_margin=0.2,
        rollback_reserve=0.3,
        evidence_ceiling=EvidenceClassification.REAL_CONTROLLED_EXPERIMENT,
        capsule_hash="capsule-a",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _actual() -> dict[str, str]:
    return {
        "tenant_id": "tenant-a",
        "manifest_hash": "manifest-a",
        "trace_root_hash": "trace-a",
        "intervention_hash": "intervention-a",
        "current_version": "v1",
        "candidate_version": "v2",
        "policy_hash": "policy-a",
        "capsule_hash": "capsule-a",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_version", "v-stale"),
        ("policy_hash", "policy-changed"),
        ("trace_root_hash", "trace-changed"),
    ],
)
def test_distributed_state_drift_blocks_before_execution(
    store_path: Path, field: str, value: str
) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)
    actual = _actual()
    actual[field] = value

    admitted, reason = store.verify(receipt.receipt_id, actual=actual)

    assert not admitted
    assert field in reason
    assert store.status(receipt.receipt_id).value == "VOIDED"
    assert [event.event_type for event in store.events(receipt.receipt_id)] == [
        "ISSUE",
        "MISMATCH_REFUSAL",
        "VOID",
    ]


def test_expired_receipt_blocks_and_is_voided(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)

    admitted, reason = store.verify(
        receipt.receipt_id,
        actual=_actual(),
        now=datetime.now(UTC) + timedelta(hours=1),
    )

    assert not admitted
    assert "expired" in reason
    assert store.status(receipt.receipt_id).value == "VOIDED"


def test_evidence_promotion_blocks_before_consume(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)

    admitted, reason = store.verify(
        receipt.receipt_id,
        actual=_actual(),
        evidence_class=EvidenceClassification.PRODUCTION,
    )

    assert not admitted
    assert "ceiling" in reason
    assert store.status(receipt.receipt_id).value == "VOIDED"


def test_receipt_survives_restart_and_single_use_claim(store_path: Path) -> None:
    path = store_path
    receipt = _receipt()
    first = AdmissionReceiptStore(path)
    first.issue(receipt)

    second = AdmissionReceiptStore(path)
    admitted, reason = second.verify(receipt.receipt_id, actual=_actual())
    admitted_again, second_reason = second.verify(receipt.receipt_id, actual=_actual())
    second.consume(receipt.receipt_id)

    assert admitted and reason == "ok"
    assert not admitted_again and "verified" in second_reason
    assert second.status(receipt.receipt_id).value == "CONSUMED"
    events = second.events(receipt.receipt_id)
    assert [event.event_type for event in events] == [
        "ISSUE",
        "VERIFY",
        "MISMATCH_REFUSAL",
        "CONSUME",
    ]
    assert all(
        event.previous_event_hash == events[index - 1].event_hash
        for index, event in enumerate(events)
        if index
    )


def test_recovery_executor_refuses_before_capsule_preparation(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)
    monkeypatch.setenv("DGX_ADMISSION_STORE_PATH", str(store_path))
    proposal = RecoveryProposal(
        action_type=RecoveryActionType.INCREASE_TOP_K,
        tenant_id="tenant-a",
        node_id="node-a",
        run_id="run-a",
        diagnosis_id="diagnosis-a",
        requester_id="worker-a",
        params={"component_id": "retriever-a", "new_top_k": 4},
        execution_mode=ExecutionMode.APPROVED,
        admission_receipt_id=receipt.receipt_id,
        admission_binding={"manifest_hash": "changed-before-remediation"},
    )
    executor = LocalDevExecutor(CapsuleRegistry())

    with pytest.raises(ValueError, match="admission boundary"):
        executor.execute_with_admission(proposal)

    assert executor._capsule_reg.for_proposal(proposal.proposal_id) is None


def test_release_and_void_are_durable_audited_transitions(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    released = _receipt()
    store.issue(released)
    store.release(released.receipt_id)

    voided = _receipt(intervention_hash="intervention-b")
    store.issue(voided)
    store.void(voided.receipt_id, reason="operator cancellation")

    assert [event.event_type for event in store.events(released.receipt_id)] == [
        "ISSUE",
        "RELEASE",
    ]
    assert [event.event_type for event in store.events(voided.receipt_id)] == [
        "ISSUE",
        "VOID",
    ]
