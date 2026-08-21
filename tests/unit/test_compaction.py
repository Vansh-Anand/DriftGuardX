import pytest
from packages.graph.src.compaction import CompactionGuard, FakeEntailmentProvider, EntailmentResult

def test_fake_entailment_provider():
    provider = FakeEntailmentProvider()
    
    # Overlap => supported
    res = provider.score("The system uses semantic embeddings.", "semantic embeddings are used.")
    assert res == EntailmentResult.SUPPORTED
    
    # No overlap => unsupported
    res = provider.score("The quick brown fox jumps.", "A completely different topic.")
    assert res == EntailmentResult.UNSUPPORTED
    
    # Explicit contradict trigger
    res = provider.score("The sky is blue.", "I contradict this.")
    assert res == EntailmentResult.CONTRADICTED
    
    # Explicit unknown trigger
    res = provider.score("Data", "This is unknown.")
    assert res == EntailmentResult.UNKNOWN

def test_compaction_guard_validation():
    guard = CompactionGuard(entailment_provider=FakeEntailmentProvider())
    guard.unsupported_threshold = 0.5
    
    original_spans = [
        {"content": "The system uses semantic embeddings for evaluation.", "trust_level": "high"}
    ]
    
    # Supported summary
    assert guard.validate_compaction(original_spans, "semantic embeddings for evaluation.", "high") is True
    
    # Contradicted summary (instant fail)
    assert guard.validate_compaction(original_spans, "This will contradict the source.", "high") is False
    
    # Mixed unsupported summary (ratio check)
    # 2 sentences: 1 supported, 1 unsupported -> ratio 0.5 <= 0.5 -> Should pass
    assert guard.validate_compaction(original_spans, "semantic embeddings for evaluation. Completely unsupported.", "high") is True
    
    # Mostly unsupported -> ratio > 0.5 -> fail
    assert guard.validate_compaction(original_spans, "semantic embeddings. Completely unsupported. Also unsupported.", "high") is False

def test_compaction_guard_trust_levels():
    guard = CompactionGuard()
    
    original_spans_mixed = [
        {"content": "verified data", "trust_level": "high"},
        {"content": "user input", "trust_level": "low"}
    ]
    
    # Cannot promote low trust to high trust
    assert guard.validate_compaction(original_spans_mixed, "verified data", "high") is False
    # But can keep it low
    assert guard.validate_compaction(original_spans_mixed, "verified data", "low") is True
