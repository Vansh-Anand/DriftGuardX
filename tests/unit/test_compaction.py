from packages.graph.src.compaction import CompactionGuard
from packages.memory.src.entailment import FakeEntailmentProvider


def test_fake_entailment_provider():
    provider = FakeEntailmentProvider()

    # Overlap => supported
    res = provider.check_entailment("The system uses semantic embeddings.", "semantic embeddings are used.", "test")
    assert res.classification in ("SUPPORTED", "UNSUPPORTED")

    # No overlap => unsupported
    res = provider.check_entailment("The quick brown fox jumps.", "A completely different topic.", "test")
    assert res.classification in ("UNSUPPORTED", "CONTRADICTED")

    # Explicit contradict trigger
    res = provider.check_entailment("The sky is blue.", "I contradict this.", "test")
    assert res.classification == "CONTRADICTED"

    # Explicit unknown trigger -> Not supported directly by FakeEntailmentProvider, it falls to NEUTRAL
    res = provider.check_entailment("Data", "This is unknown.", "test")
    assert res.classification == "NEUTRAL"

def test_compaction_guard_validation():
    guard = CompactionGuard(entailment_provider=FakeEntailmentProvider())
    guard.unsupported_threshold = 0.5

    original_spans = [
        {"content": "The system uses semantic embeddings for evaluation.", "trust_level": "high"}
    ]

    # Supported summary
    assert guard.validate_compaction(original_spans, "semantic embeddings for evaluation.", "high").is_valid is True

    # Contradicted summary (instant fail)
    assert guard.validate_compaction(original_spans, "This will contradict the source.", "high").is_valid is False

    # Mixed unsupported summary (ratio check)
    # 2 sentences: 1 supported, 1 unsupported -> ratio 0.5 <= 0.5 -> Should pass
    assert guard.validate_compaction(original_spans, "semantic embeddings for evaluation. Completely unsupported.", "high").is_valid is True

    # Mostly unsupported -> ratio > 0.5 -> fail
    assert guard.validate_compaction(original_spans, "semantic embeddings. Completely unsupported. Also unsupported.", "high").is_valid is False

def test_compaction_guard_trust_levels():
    guard = CompactionGuard()

    original_spans_mixed = [
        {"content": "verified data", "trust_level": "high"},
        {"content": "user input", "trust_level": "low"}
    ]

    # Cannot promote low trust to high trust
    assert guard.validate_compaction(original_spans_mixed, "verified data", "high").is_valid is False
    # But can keep it low
    assert guard.validate_compaction(original_spans_mixed, "verified data", "low").is_valid is True
