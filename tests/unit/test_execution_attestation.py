from dataclasses import replace
from datetime import UTC, datetime, timedelta

from packages.ledger.src.crypto import DevelopmentSigner
from packages.replay.src.execution_attestation import ExecutionAttestationV1


def _attestation() -> ExecutionAttestationV1:
    started = datetime.now(UTC)
    return ExecutionAttestationV1(
        receipt_id="receipt-a",
        receipt_binding_hash="binding-a",
        tenant_id="tenant-a",
        worker_id="worker-a",
        manifest_hash="manifest-a",
        policy_hash="policy-a",
        runtime_version="2.0.0-rc.1",
        image_digest="sha256:image-a",
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        outcome="COMPLETED",
        outcome_hash="outcome-a",
    )


def test_attestation_signature_binds_runtime_and_outcome() -> None:
    signer = DevelopmentSigner(key_id="worker-key-a")
    attestation = _attestation()
    attestation.sign(signer)

    assert attestation.verify_signature(signer.public_key_b64()) == (True, "ok")
    original_hash = attestation.attestation_hash
    attestation.outcome_hash = "tampered"
    assert attestation.attestation_hash != original_hash
    assert not attestation.verify_signature(signer.public_key_b64())[0]


def test_attestation_canonical_bytes_are_deterministic() -> None:
    first = _attestation()
    second = replace(first)

    assert first.canonical_bytes == second.canonical_bytes
    assert first.attestation_hash == second.attestation_hash
