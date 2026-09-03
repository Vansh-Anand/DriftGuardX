"""
DriftGuard-X v2 — Factual Rationale Validator
PRIVATE — All Rights Reserved.

Ensures that LLM-generated rationales do not hallucinate metrics, bounds, or versions.
Any violation causes the rationale to be rejected and falls back to deterministic templates.
"""

import re

from packages.rationale.src.models import RationaleInputContract


def extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text (integers and floats)."""
    # Matches numbers like 1, 1.5, -0.05, +2.4
    matches = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    return [float(m) for m in matches]


def get_allowed_numbers(contract: RationaleInputContract) -> set[float]:
    """Collects all valid numbers from the input contract to authorize them in the text."""
    allowed = set()
    for val in contract.metric_deltas.values():
        allowed.add(float(val))

    if contract.epsilon is not None:
        allowed.add(float(contract.epsilon))
    if contract.delta is not None:
        allowed.add(float(contract.delta))

    return allowed


def validate_factual_consistency(
    contract: RationaleInputContract, generated_text: str
) -> tuple[bool, str]:
    """
    Validates that the generated text does not hallucinate new numbers or versions.
    Returns (is_valid, reason).
    """
    # 2. Version Validation
    # If the text mentions 'vX' or standard tags, they must be original or replay tags.
    versions = re.findall(r"\bv\d+[\w.-]*\b", generated_text, re.IGNORECASE)
    allowed_versions = {contract.original_version_tag.lower(), contract.replay_version_tag.lower()}

    for v in versions:
        if v.lower() not in allowed_versions:
            # Maybe it's referring to policy version, check input for any matching string
            if v.lower() not in str(contract.model_dump()).lower():
                return False, f"Hallucinated version tag: {v} not found in evidence."

    # 1. Numeric Validation
    # Remove all version tags from text so they don't count as numeric claims
    text_no_versions = re.sub(r"\bv\d+[\w.-]*\b", "", generated_text, flags=re.IGNORECASE)

    allowed_numbers = get_allowed_numbers(contract)
    extracted = extract_numbers(text_no_versions)

    for num in extracted:
        # Ignore purely structural/formatting numbers (e.g. 2026 for dates, or generic small ints like 0, 1)
        if num in (0, 1) or num > 2000:
            continue

        # We check if the number is close to any allowed number
        is_allowed = any(abs(num - allowed) < 1e-5 for allowed in allowed_numbers)
        if not is_allowed:
            return False, f"Hallucinated numeric claim: {num} not found in evidence."

    # 3. Required Component Match
    if contract.ranked_cause_component.lower() not in generated_text.lower():
        # If the root cause isn't even mentioned, it's missing critical information.
        return False, f"Missing root cause component: {contract.ranked_cause_component}"

    return True, "Valid"
