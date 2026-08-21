"""
DriftGuard-X v2 — Context Compaction Trust-Boundary Guard
Update 8: Protect against drift during agent memory summarization.
"""
import re
import enum
from typing import List, Dict, Any, Protocol, Optional

class EntailmentResult(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"

class EntailmentProvider(Protocol):
    def score(self, premise: str, hypothesis: str) -> EntailmentResult:
        """Scores whether the premise entails the hypothesis."""
        ...

class FakeEntailmentProvider:
    """A deterministic fake entailment provider for testing."""
    def score(self, premise: str, hypothesis: str) -> EntailmentResult:
        h = hypothesis.lower()
        p = premise.lower()
        if "contradict" in h:
            return EntailmentResult.CONTRADICTED
        if "unknown" in h:
            return EntailmentResult.UNKNOWN
        # Support if words overlap significantly, else unsupported
        h_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', h))
        p_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', p))
        if not h_words:
            return EntailmentResult.SUPPORTED
        
        overlap = len(h_words.intersection(p_words))
        ratio = overlap / len(h_words)
        if ratio > 0.5:
            return EntailmentResult.SUPPORTED
        return EntailmentResult.UNSUPPORTED

class CompactionGuard:
    """
    Treats each context summary as a trust-boundary transformation.
    Carries source lineage and authority labels through compaction.
    Rejects summaries that introduce unsupported claims.
    """
    def __init__(self, entailment_provider: Optional[EntailmentProvider] = None):
        self.provider = entailment_provider if entailment_provider else FakeEntailmentProvider()
        self.unsupported_threshold = 0.3

    def validate_compaction(
        self,
        original_spans: List[Dict[str, Any]], 
        summary_text: str,
        trust_level: str
    ) -> bool:
        """
        Validates that a summary does not merge incompatible trust levels
        and maintains supported evidence.
        
        Returns True if valid, False if rejected.
        """
        # Determine the maximum trust level in the original spans
        source_trust_levels = set(span.get("trust_level", "low") for span in original_spans)
        
        # If we have mixed trust levels (e.g. user input mixed with verified DB records)
        # we must not assign a "high" trust level to the resulting summary.
        if "low" in source_trust_levels and trust_level == "high":
            return False
            
        source_text = " ".join(str(span.get("content", "")) for span in original_spans)
        
        # Segment into claims (sentences)
        # Using a very naive split for prototype, usually handled by spaCy or similar
        claims = [c.strip() for c in re.split(r'[.!?]+', summary_text) if c.strip()]
        
        if not claims:
            return True
            
        unsupported_count = 0
        
        for claim in claims:
            result = self.provider.score(premise=source_text, hypothesis=claim)
            
            # Any contradiction is an immediate fail
            if result == EntailmentResult.CONTRADICTED:
                return False
                
            if result == EntailmentResult.UNSUPPORTED:
                unsupported_count += 1
                
            # UNKNOWN is NOT classified as hallucination by default, 
            # policy dictates fail open/closed, but here we treat it neutrally.
            
        unsupported_ratio = unsupported_count / len(claims)
        
        if unsupported_ratio > self.unsupported_threshold:
            return False
            
        return True
