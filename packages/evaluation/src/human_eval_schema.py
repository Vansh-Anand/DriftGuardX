import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HumanAnnotation(BaseModel):
    reviewer_id: uuid.UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Labels
    answer_correct: bool
    evidence_sufficient: bool
    hallucinated: bool
    predicted_root_cause_correct: bool
    proposed_recovery_safe: bool

    comments: str | None = None

class ReviewerSession(BaseModel):
    pseudonym_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    rubric_version: str = "v1.0"
    consent_recorded: bool = False

class EvaluationItem(BaseModel):
    item_id: str
    # Blinded trace details, no scheduler or baseline names
    blinded_trace_context: dict[str, Any]

    annotations: list[HumanAnnotation] = Field(default_factory=list)

    @property
    def needs_adjudication(self) -> bool:
        """Returns True if there are exactly 2 reviews and they disagree on any boolean flag."""
        if len(self.annotations) != 2:
            return False

        a1 = self.annotations[0]
        a2 = self.annotations[1]

        return (
            a1.answer_correct != a2.answer_correct or
            a1.evidence_sufficient != a2.evidence_sufficient or
            a1.hallucinated != a2.hallucinated or
            a1.predicted_root_cause_correct != a2.predicted_root_cause_correct or
            a1.proposed_recovery_safe != a2.proposed_recovery_safe
        )
