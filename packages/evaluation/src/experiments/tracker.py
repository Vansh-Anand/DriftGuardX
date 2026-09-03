import logging
from contextlib import nullcontext
from typing import Any

try:
    import mlflow
except ImportError:
    mlflow = None

logger = logging.getLogger(__name__)


class MLflowTracker:
    def __init__(
        self, tracking_uri: str = "sqlite:///mlruns.db", experiment_name: str = "driftguardx"
    ):
        if mlflow is None:
            logger.warning(
                "MLflow is unavailable; experiment metrics remain in local artifacts only"
            )
        else:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment_name)

    def start_run(self, run_name: str):
        return mlflow.start_run(run_name=run_name) if mlflow is not None else nullcontext()

    def log_params(self, params: dict[str, Any]) -> None:
        if mlflow is not None:
            mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        if mlflow is not None:
            mlflow.log_metrics(metrics)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        if mlflow is not None:
            mlflow.log_artifact(local_path, artifact_path)
