import os

from packages.evaluation.src.experiments.configs import ExperimentConfig
from packages.evaluation.src.experiments.orchestrator import ExperimentOrchestrator
from packages.evaluation.src.experiments.tracker import MLflowTracker


def test_experiment_orchestration_mocked(tmp_path):
    # Set mlflow tracking uri to temp
    db_path = f"sqlite:///{tmp_path}/mlruns.db"

    config = ExperimentConfig(
        experiment_name="test_smoke", regime="retrieval-only", deterministic_seed=42
    )

    tracker = MLflowTracker(tracking_uri=db_path, experiment_name="test_exp")
    orchestrator = ExperimentOrchestrator(config, tracker)

    # Run should not throw any exception and should generate reports/raw_preds_test_smoke.json
    orchestrator.run()

    assert os.path.exists("reports/raw_preds_test_smoke.json")
