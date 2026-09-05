import inspect

from apps.worker.src.worker import (
    WorkerSettings,
    execute_bcrb_diagnosis_job,
    execute_graph_construction_job,
    execute_recovery_job,
    execute_replay_job,
    worker_healthcheck,
)


def test_worker_registers_business_jobs():
    names = {function.__name__ for function in WorkerSettings.functions}
    assert "worker_healthcheck" in names
    assert "execute_replay_job" in names
    assert "execute_graph_construction_job" in names
    assert "execute_bcrb_diagnosis_job" in names
    assert "execute_recovery_job" in names


def test_replay_job_not_stub():
    """Verify execute_replay_job contains real engine references, not hardcoded stubs."""
    src = inspect.getsource(execute_replay_job)
    # Must reference the real engine
    assert "ReplayEngine" in src
    # Must validate tenant ownership
    assert "tenant_id" in src
    # Must validate pinned state
    assert "is_fully_pinned" in src
    # Must NOT return hardcoded stub values
    assert "episodes_executed: 1" not in src
    assert '"divergence_observed": False' not in src


def test_graph_job_not_stub():
    """Verify execute_graph_construction_job uses the real GraphBuilder."""
    src = inspect.getsource(execute_graph_construction_job)
    assert "GraphBuilder" in src
    assert "nodes_json" in src
    assert "edges_json" in src
    # Must NOT use hardcoded expected_nodes/edges from payload
    assert "expected_nodes" not in src


def test_bcrb_job_not_stub():
    """Verify execute_bcrb_diagnosis_job uses the real BCRBOrchestrator."""
    src = inspect.getsource(execute_bcrb_diagnosis_job)
    assert "BCRBOrchestrator" in src
    # Must NOT return hardcoded 0.95 confidence
    assert '"confidence": 0.95' not in src
    # Must support INSUFFICIENT_EVIDENCE
    assert "INSUFFICIENT_EVIDENCE" in src
    # Must persist posterior history
    assert "posterior_history" in src


def test_recovery_job_not_stub():
    """Verify execute_recovery_job delegates to the real EndToEndRecoveryPipeline."""
    src = inspect.getsource(execute_recovery_job)
    assert "EndToEndRecoveryPipeline" in src
    # Must validate tenant
    assert "tenant_id" in src
    # Must NOT return hardcoded verification_passed=True
    assert '"verification_passed": True' not in src

