import pytest
import uuid
import json
from packages.ledger.src.crypto import DevelopmentSigner
from packages.security.src.signer import kms_provider
from packages.contracts.src.recovery_models import CryptographicSignature

@pytest.mark.security
def test_certificate_integrity_tampering():
    """
    Ensure that cryptographic signatures fail verification if the payload is tampered with.
    """
    signer = DevelopmentSigner(key_id="prod-key-v1")
    
    # Original payload
    payload_to_sign = {
        "run_id": str(uuid.uuid4()),
        "replay_episode_id": str(uuid.uuid4()),
        "intervention_id": str(uuid.uuid4()),
        "evidence_kind": "COUNTERFACTUAL_REPLAY",
        "hash": "validhash123",
    }
    
    # Deterministic JSON
    payload_str = json.dumps(payload_to_sign, sort_keys=True, separators=(",", ":"))
    signature_b64 = signer.sign(payload_str.encode("utf-8"))
    
    sig = CryptographicSignature(
        algorithm="Ed25519",
        public_key=signer.public_key_b64(),
        signature=signature_b64,
        signer_id=signer.key_id()
    )
    
    # Verify original
    assert kms_provider.verify_signature(payload_to_sign, sig) == True
    
    # Tamper payload
    tampered_payload = payload_to_sign.copy()
    tampered_payload["hash"] = "invalidhash999"
    
    # Verify tampered
    assert kms_provider.verify_signature(tampered_payload, sig) == False

    # Tamper run_id
    tampered_payload2 = payload_to_sign.copy()
    tampered_payload2["run_id"] = str(uuid.uuid4())
    assert kms_provider.verify_signature(tampered_payload2, sig) == False

from packages.contracts.src.models import RequestRun, TraceArtifact, Diagnosis, Intervention, RootCauseReport, ComponentType, InterventionType, ReplayEpisode, DiagnosisClaim
from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBStep

@pytest.mark.security
def test_hash_chain_integrity():
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    
    # 1. Run
    run = RequestRun(tenant_id=tenant_id, pipeline_id=pipeline_id)
    run.run_hash = run.compute_hash()
    
    # 2. Trace
    trace = TraceArtifact(tenant_id=tenant_id, run_id=run.id, pipeline_id=pipeline_id, spans=[], run_hash=run.run_hash)
    trace.trace_hash = trace.compute_hash()
    
    # 3. Diagnosis
    diagnosis = Diagnosis(tenant_id=tenant_id, run_id=run.id, claims=[], trace_hash=trace.trace_hash)
    diagnosis.diagnosis_hash = diagnosis.compute_hash()
    
    # 4. Candidate
    candidate = BCRBCandidate(component_type=ComponentType.RETRIEVER, intervention_type=InterventionType.ROLLBACK, diagnosis_hash=diagnosis.diagnosis_hash)
    candidate.candidate_hash = candidate.compute_hash()
    
    # 5. Replay
    replay = ReplayEpisode(tenant_id=tenant_id, run_id=run.id, swapped_component_type=ComponentType.RETRIEVER, original_version_tag="v1", replay_version_tag="v2", replay_version_id=uuid.uuid4(), candidate_hash=candidate.candidate_hash)
    replay.replay_hash = replay.compute_hash()
    
    # 6. Posterior (BCRBStep)
    step = BCRBStep(session_id=uuid.uuid4(), candidate_id=candidate.candidate_id, replay_hash=replay.replay_hash)
    step.posterior_hash = step.compute_hash()
    
    # 7. Intervention
    intervention = Intervention(run_id=run.id, tenant_id=tenant_id, target_component_type=ComponentType.RETRIEVER, intervention_type=InterventionType.ROLLBACK, from_version_id=uuid.uuid4(), to_version_id=uuid.uuid4(), from_version_tag="v2", to_version_tag="v1", posterior_hash=step.posterior_hash)
    intervention.intervention_hash = intervention.compute_hash()
    
    # 8. Report
    report = RootCauseReport(tenant_id=tenant_id, run_id=run.id, recovery_hash=intervention.intervention_hash)
    report.report_hash = report.compute_hash()
    
    assert trace.run_hash == run.run_hash
    assert report.recovery_hash == intervention.intervention_hash

@pytest.mark.security
def test_tamper_detection_breaks_chain():
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    
    run = RequestRun(tenant_id=tenant_id, pipeline_id=pipeline_id)
    run.run_hash = run.compute_hash()
    
    trace = TraceArtifact(tenant_id=tenant_id, run_id=run.id, pipeline_id=pipeline_id, spans=[], run_hash=run.run_hash)
    trace.trace_hash = trace.compute_hash()
    
    diagnosis = Diagnosis(tenant_id=tenant_id, run_id=run.id, claims=[], trace_hash=trace.trace_hash)
    diagnosis.diagnosis_hash = diagnosis.compute_hash()
    
    # Tamper the trace by modifying its content
    trace.is_synthetic = True
    new_trace_hash = trace.compute_hash()
    
    assert new_trace_hash != diagnosis.trace_hash, "Tampered trace should break link to diagnosis"

@pytest.mark.security
def test_each_artifact_fails_verification_on_mutation():
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    
    run = RequestRun(tenant_id=tenant_id, pipeline_id=pipeline_id)
    original_run_hash = run.compute_hash()
    run.status = "failed"
    assert run.compute_hash() != original_run_hash
    
    trace = TraceArtifact(tenant_id=tenant_id, run_id=run.id, pipeline_id=pipeline_id, spans=[])
    original_trace_hash = trace.compute_hash()
    trace.total_span_count = 1
    assert trace.compute_hash() != original_trace_hash

