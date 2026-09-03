"""
DriftGuard-X v2 — Context Compaction Trust-Boundary Guard
Update 8: Protect against drift during agent memory summarization.
Update 12: Real NLI Provider
"""

import re
from dataclasses import dataclass
from typing import Any

from packages.memory.src.entailment import EntailmentProvider, get_entailment_provider


@dataclass
class CompactionResult:
    is_valid: bool
    claims: list[dict[str, Any]]


class CompactionGuard:
    """
    Treats each context summary as a trust-boundary transformation.
    Carries source lineage and authority labels through compaction.
    Rejects summaries that introduce unsupported claims using Real NLI.
    """

    def __init__(
        self,
        entailment_provider: EntailmentProvider | None = None,
        fail_behavior: str = "fail_closed",
    ):
        # In production this will throw if forced to fake
        self.provider = entailment_provider if entailment_provider else get_entailment_provider()
        self.fail_behavior = fail_behavior
        self.unsupported_threshold = 0.3

    def _segment_claims(self, text: str) -> list[str]:
        # Improved segmentation logic to prevent naive punctuation splitting failure
        # e.g., Mr. Smith -> Mr, Smith.
        # For prototype, we use a basic regex that avoids splitting on common abbreviations.
        text = re.sub(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s", "\n", text)
        claims = [c.strip() for c in text.split("\n") if c.strip()]
        return claims

    def validate_compaction(
        self, original_spans: list[dict[str, Any]], summary_text: str, trust_level: str
    ) -> CompactionResult:
        """
        Validates that a summary does not merge incompatible trust levels
        and maintains supported evidence via NLI.

        Returns CompactionResult.
        """
        source_trust_levels = set(span.get("trust_level", "low") for span in original_spans)

        if "low" in source_trust_levels and trust_level == "high":
            return CompactionResult(is_valid=False, claims=[])

        # Bind source lineage to spans
        source_text = " ".join(str(span.get("content", "")) for span in original_spans)
        source_id = (
            original_spans[0].get("id", "unknown_source") if original_spans else "unknown_source"
        )

        claims = self._segment_claims(summary_text)

        if not claims:
            return CompactionResult(is_valid=True, claims=[])

        unsupported_count = 0
        recorded_claims = []

        for claim in claims:
            decision = self.provider.check_entailment(
                premise=source_text, hypothesis=claim, source_id=source_id
            )

            recorded_claims.append(
                {
                    "claim": decision.claim,
                    "confidence": decision.confidence,
                    "supporting_source_ids": decision.supporting_source_ids,
                    "classification": decision.classification,
                }
            )

            if decision.classification == "CONTRADICTED":
                return CompactionResult(is_valid=False, claims=recorded_claims)

            if decision.classification == "UNSUPPORTED":
                unsupported_count += 1

            if decision.classification == "UNKNOWN":
                if self.fail_behavior == "fail_closed":
                    return CompactionResult(is_valid=False, claims=recorded_claims)
                elif self.fail_behavior == "require_human_review":
                    return CompactionResult(
                        is_valid=False, claims=recorded_claims
                    )  # For automation, require_human_review fails open loop

        unsupported_ratio = unsupported_count / len(claims)

        if unsupported_ratio > self.unsupported_threshold:
            return CompactionResult(is_valid=False, claims=recorded_claims)

        return CompactionResult(is_valid=True, claims=recorded_claims)
