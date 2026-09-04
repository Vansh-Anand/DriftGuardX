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
