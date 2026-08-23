"""
DriftGuard-X v2 — Rationale Evaluation Suite
PRIVATE — All Rights Reserved.
"""
import uuid

import pytest

from packages.contracts.src.models import ComponentType
from packages.rationale.src.llm import generate_rationale
from packages.rationale.src.models import RationaleInputContract, RationaleStyle
from packages.rationale.src.templates import generate_template_rationale
from packages.rationale.src.validator import validate_factual_consistency


@pytest.fixture
def base_contract():
    return RationaleInputContract(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        ranked_cause_component=ComponentType.RETRIEVER,
        symptom_to_cause_path=["api", "router", "retriever"],
        root_cause_description="Suboptimal top_k setting",
        replay_episode_id=uuid.uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2-exp",
        metric_deltas={"quality": 0.05, "latency": -10.5},
        is_certified=True,
        bound_method="hoeffding",
        epsilon=0.05,
        delta=0.01,
        policy_decision="APPROVED",
        action_type="ROLLBACK",
        limitations=["Assumes independent queries"]
    )


def test_template_operator_summary(base_contract):
    """Test deterministic template covers required fields."""
    out = generate_template_rationale(base_contract, RationaleStyle.OPERATOR_SUMMARY)
    assert not out.is_llm_generated
    assert "retriever" in out.content
    assert "+0.05" in out.content
    assert "-10.5" in out.content
    assert "v2-exp" in out.content
    assert "APPROVED" in out.content
    assert "hoeffding" in out.content


def test_template_patent_note(base_contract):
    """Patent note template shouldn't include global safety claims."""
    out = generate_template_rationale(base_contract, RationaleStyle.PATENT_NOTE)
    assert "EXPERIMENT RECORD (CONFIDENTIAL)" in out.content
    assert "This does not constitute a claim of global safety" in out.content


def test_validator_detects_hallucinated_metric(base_contract):
    """Validator must reject a metric not in evidence."""
    # Evidence has quality: 0.05, latency: -10.5
    hallucinated_text = "The quality improved by 0.99, which is huge."
    is_valid, reason = validate_factual_consistency(base_contract, hallucinated_text)
    assert not is_valid
    assert "0.99" in reason


def test_validator_detects_hallucinated_version(base_contract):
    """Validator must reject a version tag not in evidence."""
    hallucinated_text = "Rolling back to v99 because retriever failed."
    is_valid, reason = validate_factual_consistency(base_contract, hallucinated_text)
    assert not is_valid
    assert "v99" in reason


def test_validator_detects_missing_component(base_contract):
    """Validator must reject if root cause component isn't mentioned."""
    text = "The system fixed the issue by rolling back to v2-exp. Metrics improved by 0.05."
    # Missing 'retriever'
    is_valid, reason = validate_factual_consistency(base_contract, text)
    assert not is_valid
    assert "Missing root cause" in reason


def test_validator_passes_valid_text(base_contract):
    text = "The retriever component was fixed by moving from v1 to v2-exp, gaining 0.05 in quality."
    is_valid, reason = validate_factual_consistency(base_contract, text)
    assert is_valid


def test_llm_fallback_on_hallucination(monkeypatch, base_contract):
    """If LLM hallucinates, system must silently fallback to template."""

    # Mock LLM to hallucinate
    def mock_invoke(*args, **kwargs):
        return "I upgraded retriever to v3, reducing latency by 999.0.", 10.0

    monkeypatch.setattr("packages.rationale.src.llm.invoke_llm", mock_invoke)

    out = generate_rationale(base_contract, use_llm=True)

    # Even though we asked for LLM, it hallucinated, so we get template fallback
    assert out.fallback_triggered is True
    assert out.factual_consistency_score == 0.0
    # Output content should be the deterministic template, not the hallucination
    assert "999.0" not in out.content
    assert "v3" not in out.content
    assert "retriever" in out.content


def test_llm_success_path(monkeypatch, base_contract):
    """If LLM generates strictly valid text, it passes through."""

    def mock_invoke(*args, **kwargs):
        return "The retriever component was fixed by moving from v1 to v2-exp, gaining 0.05 in quality.", 10.0

    monkeypatch.setattr("packages.rationale.src.llm.invoke_llm", mock_invoke)

    out = generate_rationale(base_contract, use_llm=True)

    assert out.fallback_triggered is False
    assert out.is_llm_generated is True
    assert out.factual_consistency_score == 1.0


def test_disabled_llm(base_contract):
    """When LLM is disabled, only template is used."""
    out = generate_rationale(base_contract, use_llm=False)
    assert out.is_llm_generated is False
    assert out.fallback_triggered is True


def test_undercertified_logic(base_contract):
    """Test generating rationale for an uncertified diagnosis."""
    base_contract.is_certified = False
    base_contract.bound_method = None

    out = generate_template_rationale(base_contract, RationaleStyle.OPERATOR_SUMMARY)
    assert "UNCERTIFIED" in out.content
    assert "Bound:" not in out.content
