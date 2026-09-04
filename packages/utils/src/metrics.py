from datetime import datetime
from typing import Sequence
import math

class RecoveryMetricsTracker:
    """
    Calculates operational recovery metrics across the pipeline.
    """
    
    @staticmethod
    def calculate_mttd(detection_times: Sequence[datetime], fault_times: Sequence[datetime]) -> float:
        """
        Mean Time To Detect (MTTD) in seconds.
        """
        if not detection_times or not fault_times or len(detection_times) != len(fault_times):
            return 0.0
            
        deltas = [(d - f).total_seconds() for d, f in zip(detection_times, fault_times) if d > f]
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)
        
    @staticmethod
    def calculate_mttr(recovery_times: Sequence[datetime], detection_times: Sequence[datetime]) -> float:
        """
        Mean Time To Recover (MTTR) in seconds.
        """
        if not recovery_times or not detection_times or len(recovery_times) != len(detection_times):
            return 0.0
            
        deltas = [(r - d).total_seconds() for r, d in zip(recovery_times, detection_times) if r > d]
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)

    @staticmethod
    def calculate_blast_radius(components_affected: int, total_components: int) -> float:
        """
        Calculates the blast radius of an intervention.
        """
        if total_components <= 0:
            return 0.0
        return components_affected / total_components
        
    @staticmethod
    def calculate_reliability_gain(original_score: float, replayed_score: float) -> float:
        """
        Calculates the reliability gain of a successful recovery.
        """
        return max(0.0, replayed_score - original_score)
