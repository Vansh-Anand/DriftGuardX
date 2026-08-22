from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

class EvaluationEpisode(BaseModel):
    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    expected_answer: Optional[str] = None
    relevant_chunk_ids: List[str] = Field(default_factory=list)
    difficulty: str = "medium"
    corpus_version_id: str
    
    # Fault Injection Tracking
    fault_id: Optional[str] = None
    ground_truth_root_cause: Optional[str] = None
    expected_recovery_action: Optional[str] = None
    
    # Reviewer Metadata
    reviewer_labels: Dict[str, Any] = Field(default_factory=dict)
    
    def dict_for_mlflow(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "query": self.query,
            "difficulty": self.difficulty,
            "corpus_version": self.corpus_version_id,
            "fault_id": self.fault_id or "none",
            "ground_truth_rca": self.ground_truth_root_cause or "none"
        }
