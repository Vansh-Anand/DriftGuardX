from apps.worker.src.worker import WorkerSettings, worker_healthcheck


def test_worker_does_not_advertise_false_success_business_jobs():
    assert WorkerSettings.functions == [worker_healthcheck]
    names = {function.__name__ for function in WorkerSettings.functions}
    assert "execute_run_job" not in names
    assert "execute_replay_job" not in names
