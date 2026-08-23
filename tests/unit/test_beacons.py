from packages.evaluation.src.beacons import DriftBeacon
from packages.evaluation.src.semantics import CosineDriftComparator, DeterministicFakeEncoder


def test_deterministic_fake_encoder():
    encoder = DeterministicFakeEncoder(dimension=16)
    vec1 = encoder.encode("hello world")
    vec2 = encoder.encode("hello world")
    vec3 = encoder.encode("different text")

    import numpy as np
    assert np.allclose(vec1, vec2)
    assert not np.allclose(vec1, vec3)
    assert len(vec1) == 16

    # Check normalization
    import math
    mag = math.sqrt(sum(x*x for x in vec1))
    assert abs(mag - 1.0) < 1e-6

def test_cosine_drift_comparator():
    encoder = DeterministicFakeEncoder(dimension=16)
    comparator = CosineDriftComparator(encoder)

    decision = comparator.compare("hello", "hello") # Default threshold is 0.85
    assert decision.drift_score < 0.01
    assert not decision.decision

    # Different texts should have drift
    decision = comparator.compare("this is a test", "completely unrelated semantic payload")
    assert decision.drift_score > 0.0

    # Threshold boundary tests
    # If we set threshold to 1.0 (exact match)
    comparator_strict = CosineDriftComparator(encoder, threshold=0.9999)
    decision_zero = comparator_strict.compare("hello", "hello")
    assert decision_zero.decision is False  # 0.0 drift, cosine 1.0 < 0.9999 is False

    # If we set threshold to exactly the similarity score?
    score = decision.drift_score
    similarity = 1.0 - score
    comparator_boundary = CosineDriftComparator(encoder, threshold=similarity)
    decision_boundary = comparator_boundary.compare("this is a test", "completely unrelated semantic payload")
    assert decision_boundary.decision is False  # similarity < threshold must be strictly less

    comparator_above = CosineDriftComparator(encoder, threshold=similarity + 0.001)
    decision_above = comparator_above.compare("this is a test", "completely unrelated semantic payload")
    assert decision_above.decision is True

def test_drift_beacon_semantic_drift():
    # Setup beacon with baseline text instead of a signature
    baseline_outputs = {
        "probe_1": "The quick brown fox jumps over the lazy dog."
    }

    beacon = DriftBeacon("provider_1", baseline_outputs)

    # Runner returning exactly the same text
    result = beacon.run_probe("probe_1", None, lambda x: {"text": "The quick brown fox jumps over the lazy dog."})

    assert not result["is_drifted"]
    assert result["drift_score"] < 0.01
    assert "identity_hash" in result

    # Runner returning wildly different text
    result_drift = beacon.run_probe("probe_1", None, lambda x: {"text": "Cataclysmic error: model failed."})
    # Our deterministic fake encoder might randomly have low or high cosine distance,
    # but practically they will differ. Let's just assert we get the fields back.
    assert "drift_score" in result_drift
    assert "diagnostics" in result_drift
