import datetime
import pytest
from packages.contracts.src.models import RecoveryEligibilityCertificate, serialize_for_signing
from packages.ledger.src.crypto import DevelopmentSigner
from packages.recovery.src.engine import RecoveryEngine, RecoveryRecord
from packages.recovery.src.actions import RecoveryProposal, ExecutionMode, RecoveryStatus, RecoveryActionType
from packages.recovery.src.executor import LocalDevExecutor
from packages.recovery.src.capsule import CapsuleRegistry

@pytest.fixture
def signer():
    return DevelopmentSigner(key_id="test-key")

@pytest.fixture
def valid_rec(signer):
    rec = RecoveryEligibilityCertificate(
        original_trace_root_hash="trace_123",
        manifest_hash="man_123",
        intervention_hash="int_123",
        measured_resource_budget_and_usage={"cpu": 1.0},
        replay_outcome="success",
        reliability_delta=0.5,
        policy_version="v1",
        policy_decision="approved",
        approval_decision_set=["userA_approved"],
        canary_result_hash="canary_123",
        recovery_capsule_hash="capsule_123",
        executor_image_digest="sha256:abcd",
        signer_identity=signer.key_id()
    )
    payload = serialize_for_signing(rec)
    rec.signature_b64 = signer.sign(payload)
    return rec

@pytest.fixture
def engine():
    registry = CapsuleRegistry()
    return RecoveryEngine(executor=LocalDevExecutor(capsule_registry=registry), capsule_registry=registry)

@pytest.fixture
def proposal():
    return RecoveryProposal(
        proposal_id="prop_1",
        tenant_id="00000000-0000-0000-0000-000000000000",
        run_id="00000000-0000-0000-0000-000000000000",
        node_id="node_1",
        diagnosis_id="diag_1",
        requester_id="user_1",
        action_type=RecoveryActionType.ROLLBACK_COMPONENT,
        params={"component_id": "retriever", "target_version_id": "v1", "expected_current_version_id": "v2"},
        policy_decision="approved",
        execution_mode=ExecutionMode.SIMULATION, # Mutating mode to trigger REC check
    )

def test_rec_verification_success(engine, proposal, valid_rec, signer):
    record = engine.run(
        proposal=proposal,
        canary_episodes=[],
        certificate=valid_rec,
        signer_public_key_b64=signer.public_key_b64()
    )
    # The verification step should pass.
    # It might fail later due to missing capsule or optimistic lock, so we only assert no REC failure.
    assert not any("SECURITY:" in log for log in record.escalation_log)

def test_rec_tampering(engine, proposal, valid_rec, signer):
    # Tamper with the certificate
    valid_rec.policy_decision = "denied"
    
    record = engine.run(
        proposal=proposal,
        canary_episodes=[],
        certificate=valid_rec,
        signer_public_key_b64=signer.public_key_b64()
    )
    
    assert record.machine.current_status == RecoveryStatus.FAILED
    assert any("Invalid REC signature" in log for log in record.escalation_log)

def test_rec_expired(engine, proposal, valid_rec, signer):
    # Set timestamp to 2 hours ago
    valid_rec.timestamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    
    # Resign since we modified the payload
    payload = serialize_for_signing(valid_rec)
    valid_rec.signature_b64 = signer.sign(payload)
    
    record = engine.run(
        proposal=proposal,
        canary_episodes=[],
        certificate=valid_rec,
        signer_public_key_b64=signer.public_key_b64()
    )
    
    assert record.machine.current_status == RecoveryStatus.FAILED
    assert any("Expired REC" in log for log in record.escalation_log)

def test_rec_missing(engine, proposal, signer):
    record = engine.run(
        proposal=proposal,
        canary_episodes=[],
        certificate=None,
        signer_public_key_b64=signer.public_key_b64()
    )
    
    assert record.machine.current_status == RecoveryStatus.FAILED
    assert any("No REC provided" in log for log in record.escalation_log)

def test_rec_dry_run_ignores(engine, proposal, valid_rec, signer):
    # DRY_RUN shouldn't mandate REC verification if it doesn't execute mutate
    proposal.execution_mode = ExecutionMode.DRY_RUN
    
    record = engine.run(
        proposal=proposal,
        canary_episodes=[],
        certificate=None, # Missing!
        signer_public_key_b64=signer.public_key_b64()
    )
    
    # Still succeeds / commits
    assert record.machine.current_status == RecoveryStatus.COMMITTED
