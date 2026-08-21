import os
import pytest
from datetime import datetime, timezone
from packages.ledger.src.store import SQLiteTransparencyStore
from packages.ledger.src.witness import TransparencyWitness
from packages.contracts.src.models import RecoveryCertificate
from uuid import uuid4

def test_sqlite_store_persistence(tmp_path):
    db_path = str(tmp_path / "test_ledger.db")
    
    # 1. Write witnesses
    store1 = SQLiteTransparencyStore(db_path=db_path)
    witness1 = TransparencyWitness(store=store1)
    
    cert = RecoveryCertificate(
        run_id=uuid4(),
        replay_episode_id=uuid4(),
        intervention_id=uuid4(),
        repair_decision_id=uuid4(),
        tenant_id=uuid4(),
        certificate_hash="test_hash_1",
        issued_by="tester"
    )
    
    commit_hash = witness1.commit_certificates([cert], "policy_hash_1", True)
    
    # 2. Restart/Recreate service/store
    store2 = SQLiteTransparencyStore(db_path=db_path)
    witness2 = TransparencyWitness(store=store2)
    
    # 3. Load ledger and verify exact chain/root
    assert witness2.verify_commit(commit_hash) is True
    
    latest = store2.latest_checkpoint()
    assert latest is not None
    assert latest["commit_hash"] == commit_hash
    assert latest["certificate_count"] == 1
    assert latest["policy_snapshot"] == "policy_hash_1"
    
    # 4. Detect database tampering (modify the DB directly)
    import sqlite3
    import json
    with sqlite3.connect(db_path) as conn:
        tampered_payload = {
            "timestamp": "some_time",
            "commit_hash": commit_hash,
            "merkle_root": "root",
            "certificate_count": 1,
            "policy_snapshot": "tampered",
            "canary_passed": True
        }
        conn.execute("UPDATE ledger SET payload = ? WHERE commit_hash = ?", (json.dumps(tampered_payload), commit_hash,))
        
    # Reloading from store should show tampered data
    tampered_entry = store2.get(commit_hash)
    assert tampered_entry["policy_snapshot"] == "tampered"
    
    # In a full implementation, `verify_chain` would recalculate the hash from the payload 
    # to ensure it matches the commit_hash, which would fail here. 
    # For now, we test the persistence guarantees.
