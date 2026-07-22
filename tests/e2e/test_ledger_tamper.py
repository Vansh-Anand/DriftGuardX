"""
DriftGuard-X v2 — Ledger Tamper Tests & Benchmarks
PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import json
import os
import time
import uuid
import pytest
import aiosqlite
from pathlib import Path

from packages.ledger.src.schema import RecoveryCertificate
from packages.ledger.src.crypto import DevelopmentSigner
from packages.ledger.src.chain import LedgerChain, CertificateValidationError
from packages.ledger.src.export import export_machine_bundle, export_human_summary


@pytest.fixture
def signer():
    return DevelopmentSigner(key_id="test-key-01")


@pytest.fixture
async def temp_ledger(tmp_path):
    db_path = str(tmp_path / "ledger.sqlite")
    chain = LedgerChain(db_path)
    await chain.initialize()
    yield chain
    if os.path.exists(db_path):
        os.remove(db_path)


def make_cert(signer: DevelopmentSigner, previous_hash: str) -> RecoveryCertificate:
    cert = RecoveryCertificate(
        cert_id=f"cert_{uuid.uuid4().hex[:8]}",
        tenant_id="tenant_acme",
        pipeline_id="pipeline_test",
        run_id="run_test",
        trace_before_digest="before_hash",
        trace_after_digest="after_hash",
        replay_capsule_hash="replay_hash",
        intervention_vector={"component_id": "test_comp", "param": 10},
        contribution_metrics={"quality": 0.05},
        certification_method="test",
        epsilon=0.1,
        delta=0.01,
        policy_version="v1",
        policy_reason="test",
        approvals=[],
        action_result="COMMITTED",
        verification_result="PASSED",
        rollback_capsule_digest="rollback_hash",
        previous_cert_hash=previous_hash,
    )
    # Sign it
    payload = cert.canonical_bytes()
    cert.signature = signer.sign(payload)
    cert.signer_key_id = signer.key_id()
    cert.signer_pub_key = signer.public_key_b64()
    return cert


@pytest.mark.asyncio
async def test_clean_chain_verifies(temp_ledger, signer):
    """A clean chain verifies from genesis to head."""
    cert1 = make_cert(signer, "GENESIS")
    hash1 = await temp_ledger.append_certificate(cert1)
    
    cert2 = make_cert(signer, hash1)
    hash2 = await temp_ledger.append_certificate(cert2)
    
    cert3 = make_cert(signer, hash2)
    await temp_ledger.append_certificate(cert3)
    
    assert await temp_ledger.verify_chain() is True
    assert temp_ledger.size == 3


@pytest.mark.asyncio
async def test_tamper_alter_content(temp_ledger, signer):
    """Tampering with certificate content in DB breaks verification."""
    cert1 = make_cert(signer, "GENESIS")
    await temp_ledger.append_certificate(cert1)
    
    # Manually tamper with the database bypassing the application layer
    async with aiosqlite.connect(temp_ledger.db_path) as db:
        async with db.execute("SELECT payload FROM ledger WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            payload = json.loads(row[0])
            payload["action_result"] = "COMPENSATED" # Tampered
        
        await db.execute("UPDATE ledger SET payload = ? WHERE id = 1", (json.dumps(payload),))
        await db.commit()
        
    assert await temp_ledger.verify_chain() is False


@pytest.mark.asyncio
async def test_tamper_alter_previous_hash(temp_ledger, signer):
    """Tampering with previous hash linkage breaks verification."""
    cert1 = make_cert(signer, "GENESIS")
    hash1 = await temp_ledger.append_certificate(cert1)
    
    cert2 = make_cert(signer, hash1)
    await temp_ledger.append_certificate(cert2)
    
    # Tamper with linkage in the JSON payload
    async with aiosqlite.connect(temp_ledger.db_path) as db:
        async with db.execute("SELECT payload FROM ledger WHERE id = 2") as cursor:
            row = await cursor.fetchone()
            payload = json.loads(row[0])
            payload["previous_cert_hash"] = "FAKE_HASH" # Tampered
            
        await db.execute("UPDATE ledger SET previous_hash = ?, payload = ? WHERE id = 2", ("FAKE_HASH", json.dumps(payload)))
        await db.commit()
        
    assert await temp_ledger.verify_chain() is False


@pytest.mark.asyncio
async def test_tamper_delete_historical_row(temp_ledger, signer):
    """Deleting a historical row breaks verification (missing record / fork detection)."""
    cert1 = make_cert(signer, "GENESIS")
    hash1 = await temp_ledger.append_certificate(cert1)
    
    cert2 = make_cert(signer, hash1)
    hash2 = await temp_ledger.append_certificate(cert2)
    
    cert3 = make_cert(signer, hash2)
    await temp_ledger.append_certificate(cert3)
    
    # Delete middle record
    async with aiosqlite.connect(temp_ledger.db_path) as db:
        await db.execute("DELETE FROM ledger WHERE id = 2")
        await db.commit()
        
    assert await temp_ledger.verify_chain() is False


@pytest.mark.asyncio
async def test_invalid_signature_on_append(temp_ledger, signer):
    """Appending a certificate with an invalid signature is blocked."""
    cert = make_cert(signer, "GENESIS")
    
    # Tamper with signature before append
    cert.signature = "INVALID_SIG"
    
    with pytest.raises(CertificateValidationError, match="Cryptographic signature verification failed"):
        await temp_ledger.append_certificate(cert)


@pytest.mark.asyncio
async def test_wrong_key_signature_rejected(temp_ledger, signer):
    """Appending a certificate signed by the wrong key but claiming to be someone else."""
    rogue_signer = DevelopmentSigner(key_id="rogue-key")
    cert = make_cert(rogue_signer, "GENESIS")
    
    # Impersonate public key
    cert.signer_pub_key = signer.public_key_b64()
    
    with pytest.raises(CertificateValidationError, match="Cryptographic signature verification failed"):
        await temp_ledger.append_certificate(cert)


@pytest.mark.asyncio
async def test_export_redaction(temp_ledger, signer):
    """Human export redacts sensitive fields but machine export does not."""
    # To have a valid signature with the secret, we must add it before signing.
    cert = RecoveryCertificate(
        cert_id=f"cert_{uuid.uuid4().hex[:8]}",
        tenant_id="tenant_acme",
        pipeline_id="pipeline_test",
        run_id="run_test",
        trace_before_digest="before_hash",
        trace_after_digest="after_hash",
        replay_capsule_hash="replay_hash",
        intervention_vector={"component_id": "test_comp", "param": 10, "prompt_secret": "my_secret_key"},
        contribution_metrics={"quality": 0.05},
        certification_method="test",
        epsilon=0.1,
        delta=0.01,
        policy_version="v1",
        policy_reason="test",
        approvals=[],
        action_result="COMMITTED",
        verification_result="PASSED",
        rollback_capsule_digest="rollback_hash",
        previous_cert_hash="GENESIS",
    )
    payload = cert.canonical_bytes()
    cert.signature = signer.sign(payload)
    cert.signer_key_id = signer.key_id()
    cert.signer_pub_key = signer.public_key_b64()
    
    hash1 = await temp_ledger.append_certificate(cert)
    certs = await temp_ledger.get_all_certificates()
    
    human_json = export_human_summary(certs)
    machine_json = export_machine_bundle(certs)
    
    assert "[REDACTED]" in human_json
    assert "my_secret_key" not in human_json
    
    assert "[REDACTED]" not in machine_json
    assert "my_secret_key" in machine_json


@pytest.mark.asyncio
@pytest.mark.slow
async def test_latency_scaling_benchmark(temp_ledger, signer, caplog):
    """Benchmark certificate creation and chain verification at scale."""
    import logging
    caplog.set_level(logging.INFO)
    
    N_CERTS = 100
    
    # Append Benchmark
    start_time = time.time()
    prev_hash = "GENESIS"
    for _ in range(N_CERTS):
        cert = make_cert(signer, prev_hash)
        prev_hash = await temp_ledger.append_certificate(cert)
    append_latency = time.time() - start_time
    
    # Verify Benchmark
    start_time = time.time()
    res = await temp_ledger.verify_chain()
    verify_latency = time.time() - start_time
    
    assert res is True
    
    # Record benchmark results
    avg_append = (append_latency / N_CERTS) * 1000
    avg_verify = (verify_latency / N_CERTS) * 1000
    print(f"\n[BENCHMARK] Appended {N_CERTS} certs in {append_latency:.3f}s (Avg {avg_append:.2f}ms/cert)")
    print(f"[BENCHMARK] Verified {N_CERTS} certs in {verify_latency:.3f}s (Avg {avg_verify:.2f}ms/cert)")
    
    assert avg_append < 50.0  # Should be < 50ms per cert locally
    assert avg_verify < 20.0  # Should be fast to verify
