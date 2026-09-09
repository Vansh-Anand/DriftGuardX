from concurrent.futures import ProcessPoolExecutor
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


def _verify_in_process(path: str, receipt_id: str, actual: dict[str, str]) -> bool:
    admitted, _ = AdmissionReceiptStore(path).verify(receipt_id, actual=actual)
    return admitted


def _finalize_in_process(path: str, receipt_id: str, transition: str) -> None:
    store = AdmissionReceiptStore(path)
    getattr(store, transition)(receipt_id)


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


def test_incomplete_worker_binding_blocks_before_execution(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)

    admitted, reason = store.verify(
        receipt.receipt_id,
        actual={"tenant_id": "tenant-a", "manifest_hash": "manifest-a"},
    )

    assert not admitted
    assert "incomplete" in reason
    assert "trace_root_hash" in reason
    assert store.status(receipt.receipt_id) is not None
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


def test_audit_chain_verifier_detects_persisted_mutation(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)
    admitted, _ = store.verify(receipt.receipt_id, actual=_actual())
    assert admitted
    store.consume(receipt.receipt_id)
    assert store.verify_event_chain(receipt.receipt_id) == (True, "ok")

    with store._connect() as connection:
        connection.execute(
            "UPDATE admission_audit_events SET reason = ? " "WHERE receipt_id = ? AND sequence = 2",
            ("tampered", receipt.receipt_id),
        )

    valid, reason = store.verify_event_chain(receipt.receipt_id)
    assert not valid
    assert "hash mismatch" in reason


def test_cross_process_claim_and_terminal_transition_are_single_use(store_path: Path) -> None:
    store = AdmissionReceiptStore(store_path)
    receipt = _receipt()
    store.issue(receipt)

    with ProcessPoolExecutor(max_workers=6) as pool:
        claims = list(
            pool.map(
                _verify_in_process,
                [str(store_path)] * 6,
                [receipt.receipt_id] * 6,
                [_actual() for _ in range(6)],
            )
        )

    assert claims.count(True) == 1
    with ProcessPoolExecutor(max_workers=6) as pool:
        list(
            pool.map(
                _finalize_in_process,
                [str(store_path)] * 6,
                [receipt.receipt_id] * 6,
                ["consume"] * 6,
            )
        )

    terminal_events = [
        event.event_type
        for event in store.events(receipt.receipt_id)
        if event.event_type in {"CONSUME", "RELEASE", "VOID"}
    ]
    assert terminal_events == ["CONSUME"]
    assert store.verify_event_chain(receipt.receipt_id) == (True, "ok")
