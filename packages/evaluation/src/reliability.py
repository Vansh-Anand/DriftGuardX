"""
DriftGuard-X v2 — Reliability Vector Evaluation

Computes a multi-dimensional reliability score from a trace.
These are simple, measurable baselines — not causal claims.

Dimensions:
  - faithfulness: output hash consistency across identical inputs (replay-derived)
  - latency_ok: latency within configured threshold
  - policy_pass: all policy checks passed
  - error_free: no errors in any span
  - token_budget: within token budget

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.contracts.src.models import SpanRecord, TraceArtifact


@dataclass
class ReliabilityConfig:
    """Configurable thresholds for reliability scoring."""
    max_latency_ms: float = 5000.0
    max_tokens_total: int = 4096
    latency_weight: float = 0.2
    policy_weight: float = 0.3
    error_weight: float = 0.3
    token_weight: float = 0.1
    faithfulness_weight: float = 0.1  # only meaningful in replay comparison

    def validate(self) -> None:
        total = (
            self.latency_weight
            + self.policy_weight
            + self.error_weight
            + self.token_weight
            + self.faithfulness_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


DEFAULT_CONFIG = ReliabilityConfig()


def compute_reliability_vector(
    trace: TraceArtifact,
    *,
    config: ReliabilityConfig = DEFAULT_CONFIG,
    faithfulness_score: float | None = None,
) -> dict[str, float]:
    """
    Compute a reliability vector for a trace.
    Returns dict of dimension -> score (all 0.0–1.0).

    These scores are MEASURED from the trace data.
    No causal inferences are made here.
    """
    spans = trace.spans

    # Latency: fraction of spans within threshold
    latency_scores: list[float] = []
    for span in spans:
        if span.latency_ms is not None:
            score = min(1.0, config.max_latency_ms / max(span.latency_ms, 1.0))
            latency_scores.append(min(score, 1.0))
    latency_ok = sum(latency_scores) / len(latency_scores) if latency_scores else 1.0

    # Policy: fraction of spans with policy_result == "allow" (or no policy)
    policy_spans = [s for s in spans if s.policy_result is not None]
    if policy_spans:
        policy_pass = sum(1 for s in policy_spans if s.policy_result == "allow") / len(policy_spans)
    else:
        policy_pass = 1.0  # no policy checks = not penalized

    # Error: 1.0 if no errors, 0.0 if any error
    error_spans = [s for s in spans if s.error_type is not None]
    error_free = 1.0 if not error_spans else max(0.0, 1.0 - len(error_spans) / len(spans))

    # Token budget
    total_tokens = sum(
        (s.token_count_input or 0) + (s.token_count_output or 0) for s in spans
    )
    token_budget = min(1.0, config.max_tokens_total / max(total_tokens, 1)) if total_tokens > 0 else 1.0

    # Faithfulness (only meaningful in replay — passed in externally)
    faithfulness = faithfulness_score if faithfulness_score is not None else 1.0

    return {
        "latency_ok": round(latency_ok, 4),
        "policy_pass": round(policy_pass, 4),
        "error_free": round(error_free, 4),
        "token_budget": round(token_budget, 4),
        "faithfulness": round(faithfulness, 4),
    }


def aggregate_reliability_score(
    vector: dict[str, float],
    *,
    config: ReliabilityConfig = DEFAULT_CONFIG,
) -> float:
    """
    Aggregate reliability vector into a single scalar score (0.0–1.0).
    Uses configurable weighted average.
    """
    weights = {
        "latency_ok": config.latency_weight,
        "policy_pass": config.policy_weight,
        "error_free": config.error_weight,
        "token_budget": config.token_weight,
        "faithfulness": config.faithfulness_weight,
    }
    score = sum(vector.get(k, 0.0) * w for k, w in weights.items())
    return round(min(max(score, 0.0), 1.0), 4)


def compute_reliability_delta(
    before: dict[str, float],
    after: dict[str, float],
) -> dict[str, float]:
    """Compute per-dimension delta (after - before)."""
    all_keys = set(before) | set(after)
    return {k: round(after.get(k, 0.0) - before.get(k, 0.0), 4) for k in sorted(all_keys)}
