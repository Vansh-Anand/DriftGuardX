"""
Unit tests: EvidentiaryStoppingRule.
Tests all stopping criteria: posterior confidence, margin, entropy convergence,
information exhaustion, minimum evidence count, and resource limits.
"""
import os
import math
import pytest

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-key")

from packages.contracts.src.interfaces import ResourceContext
from packages.replay.src.stopping_rule import EvidentiaryStoppingRule


class _MockBeliefModel:
    def __init__(self, beliefs: dict) -> None:
        self._beliefs = beliefs

    def current_beliefs(self) -> dict:
        return self._beliefs

    def entropy(self) -> float:
        h = 0.0
        for p in self._beliefs.values():
            if p > 0:
                h -= p * math.log2(p)
        return max(0.0, h)

    def update_belief(self, state, replays):
        return self._beliefs


class TestEvidentiaryStoppingRule:
    def _rule(self, **kwargs) -> EvidentiaryStoppingRule:
        defaults = {
            "confidence_threshold": 0.85,
            "margin_threshold": 0.60,
            "entropy_convergence_delta": 0.01,
            "entropy_window": 3,
            "min_eig_threshold": 0.01,
            "min_replays": 2,
            "max_experiments": 20,
        }
        defaults.update(kwargs)
        return EvidentiaryStoppingRule(**defaults)

    def test_resource_exhaustion_stops_immediately(self):
        rule = self._rule()
        ctx = ResourceContext(budget_usd=0.0)
        ctx.spent_usd = 0.0  # budget is 0 so any more is exhausted
        ctx.elapsed_seconds = 999.0
        model = _MockBeliefModel({"a": 0.5, "b": 0.5})
        stop, reason = rule.is_sufficient(None, ctx, model, [{"id": "x"}])
        assert stop
        assert "budget" in reason.lower() or "time" in reason.lower() or "limit" in reason.lower()

    def test_safety_cap_stops(self):
        rule = self._rule(max_experiments=3)
        ctx = ResourceContext(budget_usd=100.0)
        ctx.replay_count = 3
        model = _MockBeliefModel({"a": 0.5, "b": 0.5})
        stop, reason = rule.is_sufficient(None, ctx, model, [])
        assert stop
        assert "cap" in reason.lower() or "3" in reason

    def test_high_posterior_confidence_stops(self):
        rule = self._rule(confidence_threshold=0.85, min_replays=1)
        rule._replay_count = 2  # meet min evidence
        rule.record_iteration(1.0)
        rule.record_iteration(0.5)
        ctx = ResourceContext(budget_usd=10.0)
        model = _MockBeliefModel({"retriever": 0.90, "model": 0.10})
        stop, reason = rule.is_sufficient(None, ctx, model, [{"id": "x"}])
        assert stop
        assert "confidence" in reason.lower() or "0.9" in reason

    def test_insufficient_posterior_does_not_stop(self):
        rule = self._rule(confidence_threshold=0.85, min_replays=3)
        rule._replay_count = 1  # below min_replays
        ctx = ResourceContext(budget_usd=10.0)
        model = _MockBeliefModel({"a": 0.6, "b": 0.4})
        stop, _ = rule.is_sufficient(None, ctx, model, [{"id": "x"}, {"id": "y"}])
        assert not stop

    def test_margin_threshold_stops(self):
        rule = self._rule(margin_threshold=0.50, min_replays=1)
        rule._replay_count = 2
        rule.record_iteration(0.9)
        rule.record_iteration(0.5)
        ctx = ResourceContext(budget_usd=10.0)
        # Top-2 margin = 0.75 - 0.15 = 0.60 > 0.50
        model = _MockBeliefModel({"a": 0.75, "b": 0.15, "c": 0.10})
        stop, reason = rule.is_sufficient(None, ctx, model, [{"id": "x"}])
        assert stop
        assert "margin" in reason.lower()

    def test_entropy_convergence_stops(self):
        rule = self._rule(entropy_convergence_delta=0.1, entropy_window=3, min_replays=1)
        rule._replay_count = 4
        # Record stable entropy values
        for _ in range(4):
            rule.record_iteration(0.500)
        ctx = ResourceContext(budget_usd=10.0)
        model = _MockBeliefModel({"a": 0.55, "b": 0.45})
        stop, reason = rule.is_sufficient(None, ctx, model, [{"id": "x"}])
        assert stop
        assert "entropy" in reason.lower()

    def test_no_remaining_candidates_stops(self):
        rule = self._rule()
        ctx = ResourceContext(budget_usd=10.0)
        model = _MockBeliefModel({"a": 0.5, "b": 0.5})
        stop, reason = rule.is_sufficient(None, ctx, model, [])
        assert stop
        assert "candidate" in reason.lower() or "remaining" in reason.lower()

    def test_reset_clears_state(self):
        rule = self._rule()
        rule.record_iteration(0.9)
        rule.record_iteration(0.8)
        rule._replay_count = 5
        rule.reset()
        assert rule._replay_count == 0
        assert len(rule._entropy_history) == 0
