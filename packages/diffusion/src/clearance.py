"""
DriftGuard-X v2 - GAT Trajectory Clearance
"""
import uuid

from packages.diffusion.src.contracts import GraphDiffusionResult
from packages.replay.src.vti_coordinator import vti_coordinator


class GATClearanceOracle:
    """
    Clears or blocks an agent's reasoning trajectory based on Graph Attention Network (GAT) 
    drift detection scores. Connects to the Two-Phase Commit VTI Coordinator.
    """
    def __init__(self, drift_threshold: float = 0.5):
        """
        :param drift_threshold: Maximum acceptable root_probability / symptom_probability 
                                before a trajectory is flagged for rollback.
        """
        self.drift_threshold = drift_threshold

    def evaluate_trajectory(self, trace_id: str, diffusion_result: GraphDiffusionResult) -> bool:
        """
        Evaluates the GAT output for a trace.
        If all nodes show drift below the threshold, issues a cryptographic clearance signature 
        to the VTI to COMMIT the staged actions.
        Otherwise, triggers an instant ROLLBACK in the VTI.
        """
        # 1. Analyze GAT outputs
        max_drift_prob = 0.0
        for node_id, output in diffusion_result.node_outputs.items():
            if output.root_probability > max_drift_prob:
                max_drift_prob = output.root_probability
            if output.symptom_probability > max_drift_prob:
                max_drift_prob = output.symptom_probability

        # 2. Decision logic
        if max_drift_prob < self.drift_threshold:
            # Trajectory is mathematically cleared. Emit a signature.
            clearance_signature = f"GAT-CLEAR-{uuid.uuid4().hex}"
            return vti_coordinator.commit_action(trace_id, clearance_signature)
        else:
            # Drift detected. Instantly rollback any staged real-world actions.
            return vti_coordinator.rollback_action(trace_id)
