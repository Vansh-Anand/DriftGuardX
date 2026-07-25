import mlflow
import os
from typing import Dict, Any

class MLflowTracker:
    def __init__(self, tracking_uri: str = "sqlite:///mlruns.db", experiment_name: str = "driftguardx"):
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        
    def start_run(self, run_name: str):
        return mlflow.start_run(run_name=run_name)

    def log_params(self, params: Dict[str, Any]):
        mlflow.log_params(params)

    def log_metrics(self, metrics: Dict[str, float]):
        mlflow.log_metrics(metrics)
        
    def log_artifact(self, local_path: str, artifact_path: str = None):
        mlflow.log_artifact(local_path, artifact_path)
