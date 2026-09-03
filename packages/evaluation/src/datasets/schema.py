import uuid
from typing import Any

from pydantic import BaseModel, Field


class EvaluationEpisode(BaseModel):
    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    expected_answer: str | None = None
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    corpus_version_id: str

    # Fault Injection Tracking
    fault_id: str | None = None
    ground_truth_root_cause: str | None = None
    expected_recovery_action: str | None = None

    # Reviewer Metadata
    reviewer_labels: dict[str, Any] = Field(default_factory=dict)

    def dict_for_mlflow(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "query": self.query,
            "difficulty": self.difficulty,
            "corpus_version": self.corpus_version_id,
            "fault_id": self.fault_id or "none",
            "ground_truth_rca": self.ground_truth_root_cause or "none",
        }
