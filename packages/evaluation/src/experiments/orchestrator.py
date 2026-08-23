import json
import logging
import os

from packages.evaluation.src.datasets.adapters import BEIRAdapter, ToolBenchAdapter
from packages.evaluation.src.datasets.fault_overlays import FaultOverlay
from packages.evaluation.src.experiments.configs import ExperimentConfig
from packages.evaluation.src.experiments.tracker import MLflowTracker

logger = logging.getLogger(__name__)

class ExperimentOrchestrator:
    def __init__(self, config: ExperimentConfig, tracker: MLflowTracker):
        self.config = config
        self.tracker = tracker

    def run(self):
        with self.tracker.start_run(run_name=self.config.experiment_name):
            self.tracker.log_params(self.config.model_dump())

            logger.info(f"Running {self.config.experiment_name} under {self.config.regime} regime.")

            # 1. Fetch data
            if self.config.regime in ["retrieval-only", "rag"]:
                adapter = BEIRAdapter()
            elif self.config.regime == "tool-use":
                adapter = ToolBenchAdapter()
            else:
                adapter = BEIRAdapter() # Fallback

            clean_episodes = adapter.get_dataset()

            # 2. Inject Fault Overlay
            overlay = FaultOverlay(seed=self.config.deterministic_seed)
            drifted_episodes = overlay.apply_overlay(clean_episodes)

            # Resume & Checkpointing setup
            os.makedirs("reports", exist_ok=True)
            checkpoint_file = f"reports/checkpoint_{self.config.experiment_name}.json"

            raw_predictions = []
            start_index = 0
            if os.path.exists(checkpoint_file):
                with open(checkpoint_file) as f:
                    raw_predictions = json.load(f)
                    start_index = len(raw_predictions)
                    logger.info(f"Resuming from index {start_index}")

            successes = sum(1 for p in raw_predictions if p.get("status") == "SUCCESS")

            # 3. Simulate Evaluation & Logging failures explicitly
            provider_quota_usd = 50.0  # Provider quota mock

            for i, ep in enumerate(drifted_episodes[start_index:]):
                # Budget caps & quotas
                cost_so_far = (start_index + i + 1) * 0.05
                if cost_so_far > self.config.budget_cap_usd:
                    raw_predictions.append({"episode_id": str(ep.replay_id), "status": "BUDGET_EXCEEDED", "result": None})
                    break
                if cost_so_far > provider_quota_usd:
                    raw_predictions.append({"episode_id": str(ep.replay_id), "status": "QUOTA_EXCEEDED", "result": None})
                    break

                # Simulate success based on overlay
                rel_vector = ep.original_reliability_vector
                metric_val = sum(rel_vector.values()) / max(len(rel_vector), 1)
                is_success = metric_val > 0.5
                if is_success:
                    successes += 1

                raw_predictions.append({"episode_id": str(ep.replay_id), "status": "SUCCESS" if is_success else "FAILURE", "metrics": rel_vector})

                # Update checkpoint
                with open(checkpoint_file, "w") as f:
                    json.dump(raw_predictions, f)

            # 4. Final Raw Predictions (Sharding could split this loop)
            pred_file = f"reports/raw_preds_{self.config.experiment_name}.json"
            with open(pred_file, "w") as f:
                json.dump(raw_predictions, f)
            self.tracker.log_artifact(pred_file)

            # 5. Log metrics
            if len(raw_predictions) > 0:
                self.tracker.log_metrics({"success_rate": successes / len(raw_predictions)})
            else:
                self.tracker.log_metrics({"success_rate": 0.0})
