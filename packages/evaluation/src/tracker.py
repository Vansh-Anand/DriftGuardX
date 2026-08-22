import os
import json
import logging
from typing import Dict, Any

try:
    import mlflow
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

logger = logging.getLogger(__name__)

class Tracker:
    def __init__(self, experiment_name: str = "DriftGuard-X-Benchmarks"):
        self.experiment_name = experiment_name
        self.results_dir = os.path.join(os.getcwd(), "results", "benchmark_runs")
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.use_mlflow = HAS_MLFLOW
        if self.use_mlflow:
            mlflow.set_tracking_uri("sqlite:///mlruns.db")
            mlflow.set_experiment(self.experiment_name)
            
    def log_episode(self, episode_data: Dict[str, Any], metrics: Dict[str, float], run_id: str):
        # 1. Local JSON File Logging (MinIO equivalent for local runs)
        run_file = os.path.join(self.results_dir, f"run_{run_id}.json")
        payload = {
            "episode": episode_data,
            "metrics": metrics
        }
        with open(run_file, "w") as f:
            json.dump(payload, f, indent=2, default=str)
            
        # 2. MLflow Tracking
        if self.use_mlflow:
            try:
                with mlflow.start_run(run_name=f"episode_{run_id}"):
                    # Log parameters
                    mlflow.log_params({
                        k: v for k, v in episode_data.items() 
                        if isinstance(v, (str, int, float, bool))
                    })
                    # Log metrics
                    mlflow.log_metrics(metrics)
                    # Log artifact
                    mlflow.log_artifact(run_file)
            except Exception as e:
                logger.error(f"MLflow logging failed: {e}")
