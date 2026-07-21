"""
DriftGuard-X v2 — Worker / Background Job Tests (3 tests)

Tests the ARQ-style job execution logic without requiring a live Redis instance.
Uses deterministic mock execution.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.api.src.pipeline.mock_rag import (
    PIPELINE_WITH_EXPERIMENTAL_RETRIEVER,
    PIPELINE_WITH_STABLE_RETRIEVER,
    MockRAGPipeline,
)
from packages.contracts.src.models import RunStatus, ComponentType


@pytest.mark.unit
def test_mock_pipeline_stable_run_completes() -> None:
    """Stable pipeline execution completes without error."""
    run_id = uuid.uuid4()
    pipeline = MockRAGPipeline(PIPELINE_WITH_STABLE_RETRIEVER)
    run, trace = pipeline.execute(run_id=run_id, query="test query", seed=42, is_synthetic=True)

    assert run.status == RunStatus.COMPLETED
    assert run.error_type is None
    assert run.reliability_score is not None
    assert run.reliability_score > 0.0
    assert len(trace.spans) >= 2  # at least root + 1 component


@pytest.mark.unit
def test_mock_pipeline_experimental_run_has_lower_faithfulness() -> None:
    """Experimental pipeline run should have lower faithfulness than stable."""
    run_id_exp = uuid.uuid4()
    run_id_stable = uuid.uuid4()

    pipeline_exp = MockRAGPipeline(PIPELINE_WITH_EXPERIMENTAL_RETRIEVER)
    pipeline_stable = MockRAGPipeline(PIPELINE_WITH_STABLE_RETRIEVER)

    run_exp, _ = pipeline_exp.execute(run_id=run_id_exp, query="AI safety?", seed=42, is_synthetic=True)
    run_stable, _ = pipeline_stable.execute(run_id=run_id_stable, query="AI safety?", seed=42, is_synthetic=True)

    # Faithfulness dimension must be lower for experimental
    exp_fidelity = run_exp.reliability_vector.get("faithfulness", 1.0)
    stable_fidelity = run_stable.reliability_vector.get("faithfulness", 1.0)
    assert exp_fidelity < stable_fidelity, (
        f"Experimental faithfulness {exp_fidelity} should be < stable {stable_fidelity}"
    )


@pytest.mark.unit
def test_mock_pipeline_is_deterministic_same_seed() -> None:
    """Same seed must produce identical reliability scores."""
    pipeline = MockRAGPipeline(PIPELINE_WITH_STABLE_RETRIEVER)
    run1, _ = pipeline.execute(run_id=uuid.uuid4(), query="What is AI?", seed=42, is_synthetic=True)
    run2, _ = pipeline.execute(run_id=uuid.uuid4(), query="What is AI?", seed=42, is_synthetic=True)

    assert run1.reliability_score == run2.reliability_score, (
        f"Expected identical scores with same seed: {run1.reliability_score} vs {run2.reliability_score}"
    )
    assert run1.reliability_vector == run2.reliability_vector
