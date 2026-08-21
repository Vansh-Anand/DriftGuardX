"""
DriftGuard-X v2 — E2E tests for Adversarial Provenance Quarantine.
"""
import pytest
from uuid import uuid4

from packages.recovery.src.actions import ACTION_REGISTRY, RecoveryActionType, RecoveryProposal

def test_quarantine_provenance_partition_action_exists():
    assert RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION in ACTION_REGISTRY
    action_def = ACTION_REGISTRY[RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION]
    assert action_def.risk_tier == "medium"
    assert "partition_id" in action_def.required_params
    assert "document_set" in action_def.optional_params

def test_recovery_proposal_validation_for_quarantine():
    proposal = RecoveryProposal(
        action_type=RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION,
        tenant_id=str(uuid4()),
        node_id="test_node",
        run_id=str(uuid4()),
        diagnosis_id=str(uuid4()),
        requester_id="system",
        params={
            "partition_id": "test_partition",
            "document_set": "kb-v2"
        }
    )
    
    errors = proposal.validate_params()
    assert len(errors) == 0

def test_recovery_proposal_missing_partition_id():
    proposal = RecoveryProposal(
        action_type=RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION,
        tenant_id=str(uuid4()),
        node_id="test_node",
        run_id=str(uuid4()),
        diagnosis_id=str(uuid4()),
        requester_id="system",
        params={
            "document_set": "kb-v2"
        }
    )
    
    errors = proposal.validate_params()
    assert len(errors) == 1
    assert "Missing required param: 'partition_id'" in errors[0]


def test_provenance_quarantine_end_to_end(caplog):
    from packages.memory.src.store import global_provenance_store
    from packages.policy.src.hooks import QuarantineEnforcementError
    from packages.recovery.src.executor import LocalDevExecutor
    from packages.recovery.src.capsule import CapsuleRegistry
    from packages.replay.src.engine import MockMemoryReadV1
    from packages.contracts.src.models import ComponentType, ComponentVersion, ComponentVersionState
    import uuid
    import logging
    
    caplog.set_level(logging.INFO)
    
    global_provenance_store.clear()
    
    tenant_id = "tenant_test"
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    partition_id = f"{tenant_id}_{run_id}"
    
    # 1. Create data
    global_provenance_store.write(partition_id, {"key": "val"}, tenant_id=tenant_id)
    
    # 2. Confirm readability
    entries = global_provenance_store.read(partition_id, tenant_id=tenant_id)
    assert len(entries) == 1
    
    # 3. Quarantine
    executor = LocalDevExecutor(CapsuleRegistry())
    from packages.recovery.src.actions import ExecutionMode
    proposal = RecoveryProposal(
        action_type=RecoveryActionType.QUARANTINE_PROVENANCE_PARTITION,
        tenant_id=tenant_id,
        node_id="node",
        run_id="run",
        diagnosis_id="diag",
        requester_id="admin",
        execution_mode=ExecutionMode.APPROVED,
        params={"partition_id": partition_id}
    )
    res = executor.execute(proposal)
    assert res.success is True
    
    # 4. Test normal read (deny)
    with pytest.raises(QuarantineEnforcementError):
        global_provenance_store.read(partition_id, tenant_id=tenant_id)
        
    # 5. Test indirect read-through (deny)
    reader = MockMemoryReadV1()
    version = ComponentVersion(
        id=uuid.uuid4(), 
        component_type=ComponentType.MEMORY_READ, 
        version_tag="v1", 
        state=ComponentVersionState.STABLE, 
        config_hash="x", 
        description=""
    )
    
    with pytest.raises(QuarantineEnforcementError):
        reader.execute({"partition_id": partition_id, "tenant_id": tenant_id}, version=version)
        
    # 6. Test cached access (deny) 
    with pytest.raises(QuarantineEnforcementError):
        reader.execute({"partition_id": partition_id, "tenant_id": tenant_id, "cached": True}, version=version)
    
    # 7. Test authorized forensic access (log)
    entries_forensic = global_provenance_store.read(partition_id, tenant_id=tenant_id, requester_role="forensic_auditor")
    assert len(entries_forensic) == 1
    assert "Authorized read access to quarantined partition" in caplog.text
    
    # 8. Test unquarantine (restore)
    # Rollback via executor
    capsule = executor._capsule_reg.get(res.capsule_id)
    comp_res = executor.compensate(capsule)
    assert comp_res.success is True
    
    entries_restored = global_provenance_store.read(partition_id, tenant_id=tenant_id)
    assert len(entries_restored) == 1
