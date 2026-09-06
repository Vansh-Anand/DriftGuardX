from packages.replay.src.divergence_validator import _check_tolerance


def test_semantic_text_tolerance():
    # Minor changes should pass if threshold is slightly lower than exact
    orig = "The system is healthy."
    replay = "The system is healthy!"

    constraints = {"*": {"type": "semantic_text", "threshold": 0.95}}
    passes, reason = _check_tolerance("node1", orig, replay, constraints)
    assert passes is True

    # Major changes should fail
    replay2 = "The system has critically failed."
    passes, reason = _check_tolerance("node1", orig, replay2, constraints)
    assert passes is False
    assert "Semantic text similarity" in reason


def test_jaccard_overlap_tolerance():
    orig_list = [{"id": 1, "val": "A"}, {"id": 2, "val": "B"}]
    replay_list = [{"id": 1, "val": "A"}, {"id": 2, "val": "C"}]

    constraints = {"*": {"type": "jaccard_overlap", "threshold": 0.5}}
    passes, reason = _check_tolerance("node1", orig_list, replay_list, constraints)
    assert passes is True

    # Completely disjoint
    replay_disjoint = [{"id": 3, "val": "C"}, {"id": 4, "val": "D"}]
    passes, reason = _check_tolerance("node1", orig_list, replay_disjoint, constraints)
    assert passes is False
    assert "Jaccard overlap" in reason
