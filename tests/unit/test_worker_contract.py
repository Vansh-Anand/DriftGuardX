from apps.worker.src.worker import WorkerSettings, worker_healthcheck


def test_worker_registers_business_jobs():
    names = {function.__name__ for function in WorkerSettings.functions}
    assert "worker_healthcheck" in names
    assert "execute_replay_job" in names
    assert "execute_graph_construction_job" in names
    assert "execute_bcrb_diagnosis_job" in names
    assert "execute_recovery_job" in names
