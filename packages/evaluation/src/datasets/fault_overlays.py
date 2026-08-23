import random

from packages.contracts.src.models import ReplayEpisode


class FaultOverlay:
    """
    Injects controlled component drift without corrupting original benchmark files.
    """
    def __init__(self, seed: int = 42, drift_severity: float = 0.5):
        self.seed = seed
        self.drift_severity = drift_severity
        random.seed(self.seed)

    def apply_overlay(self, episodes: list[ReplayEpisode]) -> list[ReplayEpisode]:
        # Perturbs the original benchmark data (e.g. dropping metrics or adding noise)
        drifted = []
        for ep in episodes:
            new_ep = ep.model_copy(deep=True)
            if random.random() < self.drift_severity:
                # Inject drift
                if "relevance" in new_ep.original_reliability_vector:
                    new_ep.original_reliability_vector["relevance"] *= random.random()
                    new_ep.replay_reliability_vector["relevance"] *= random.random()
                if "tool_accuracy" in new_ep.original_reliability_vector:
                    new_ep.original_reliability_vector["tool_accuracy"] *= random.random()
                    new_ep.replay_reliability_vector["tool_accuracy"] *= random.random()
            drifted.append(new_ep)
        return drifted
