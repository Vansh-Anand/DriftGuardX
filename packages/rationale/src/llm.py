"""
DriftGuard-X v2 — LLM Rationale Generation
PRIVATE — All Rights Reserved.

Optional LLM rationale adapter that receives structured fields and strict instructions.
Includes deterministic fallback if factual validation fails.
"""

import json
import logging
import os

from packages.rationale.src.models import RationaleInputContract, RationaleOutput, RationaleStyle
from packages.rationale.src.templates import generate_template_rationale
from packages.rationale.src.validator import validate_factual_consistency

logger = logging.getLogger(__name__)


def redact_input(contract: RationaleInputContract) -> dict:
    """Scrub sensitive IDs and PII before sending to an external LLM."""
    dump = contract.model_dump(mode="json")
    # Redact raw UUIDs that might contain system traces
    dump["run_id"] = "[REDACTED_RUN_ID]"
    dump["tenant_id"] = "[REDACTED_TENANT_ID]"
    dump["replay_episode_id"] = "[REDACTED_REPLAY_ID]"
    return dump


def build_system_prompt(style: RationaleStyle) -> str:
    """Creates a strict system prompt preventing hallucination."""
    base = (
        "You are the DriftGuard-X recovery rationale generator. "
        "Your job is to translate the provided JSON evidence into a fluent natural language summary.\n"
        "STRICT RULES:\n"
        "1. DO NOT invent, hallucinate, or alter any numeric metrics.\n"
        "2. DO NOT invent or alter any version tags (v1, etc).\n"
        "3. DO NOT invent causes, approvals, or legal conclusions.\n"
        "4. DO NOT include any information not present in the JSON.\n"
    )
    if style == RationaleStyle.OPERATOR_SUMMARY:
        return base + "Style: Concise, actionable summary for an SRE operator."
    elif style == RationaleStyle.EXECUTIVE_SUMMARY:
        return (
            base
            + "Style: High-level business summary focusing on metrics and policy decisions. Avoid deep technical jargon."
        )
    elif style == RationaleStyle.INCIDENT_TICKET:
        return base + "Style: Structured incident ticket format (Root Cause, Action, Resolution)."
    elif style == RationaleStyle.PATENT_NOTE:
        return (
            base
            + "Style: Highly technical experiment record. Avoid legal advice or global safety claims."
        )
    return base


def invoke_llm(prompt: str, json_evidence: str, model: str = "mock") -> tuple[str, float]:
    """
    Invokes the LLM using ProviderRegistry.
    In real mode (DGX_REAL_MODE=1), strictly enforces real providers.
    """
    import asyncio

    from packages.rag_pipeline.src.providers import ProviderRegistry

    real_mode = os.getenv("DGX_REAL_MODE") == "1"

    registry = ProviderRegistry()

    # Check if we should use a real provider
    use_real = real_mode or (os.getenv("DGX_USE_REAL_LLM") == "1" and os.getenv("OPENAI_API_KEY"))

    if use_real:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("real_mode is enabled but OPENAI_API_KEY is not set.")
        provider = registry.get_provider("openai")
    else:
        if real_mode:
            raise RuntimeError("real_mode is enabled but mock fallback was attempted.")
        provider = registry.get_provider("local-deterministic")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(
                    asyncio.run,
                    provider.generate(prompt=prompt, context=[f"Evidence:\n{json_evidence}"]),
                ).result()
        else:
            res = loop.run_until_complete(
                provider.generate(prompt=prompt, context=[f"Evidence:\n{json_evidence}"])
            )
    except RuntimeError:
        res = asyncio.run(provider.generate(prompt=prompt, context=[f"Evidence:\n{json_evidence}"]))

    if not use_real:
        data = json.loads(json_evidence)
        content = (
            f"The LLM analyzed the issue in {data['ranked_cause_component']}. "
            f"Switching {data['original_version_tag']} to {data['replay_version_tag']} "
            f"caused metric shifts. (Mock generated text)"
        )
        latency = res.metadata.get("latency_ms", 0.0)
    else:
        content = res.text
        latency = res.metadata.get("latency_ms", 0.0)

    return content, latency


def generate_rationale(
    contract: RationaleInputContract,
    style: RationaleStyle = RationaleStyle.OPERATOR_SUMMARY,
    use_llm: bool = True,
) -> RationaleOutput:
    """
    Main entrypoint. Tries LLM generation, validates facts, falls back to templates if needed.
    """
    if not use_llm:
        return generate_template_rationale(contract, style)

    try:
        # 1. Redact inputs
        scrubbed = redact_input(contract)

        # 2. Build prompts
        sys_prompt = build_system_prompt(style)

        # 3. Call LLM
        model_version = "mock-1.0" if not os.getenv("DGX_USE_REAL_LLM") else "gpt-4o"
        content, latency = invoke_llm(sys_prompt, json.dumps(scrubbed), model=model_version)

        # 4. Validate output
        is_valid, reason = validate_factual_consistency(contract, content)

        if not is_valid:
            logger.warning(f"LLM rationale failed validation: {reason}. Falling back to template.")
            fallback = generate_template_rationale(contract, style)
            fallback.factual_consistency_score = 0.0
            fallback.latency_ms = latency
            fallback.prompt_version = "v1"
            fallback.model_version = model_version
            return fallback

        # 5. Return success
        return RationaleOutput(
            input_contract_id=contract.id,
            style=style,
            content=content,
            is_llm_generated=True,
            fallback_triggered=False,
            factual_consistency_score=1.0,
            prompt_version="v1",
            model_version=model_version,
            latency_ms=latency,
            cost_usd=0.001,  # Mock cost
        )

    except Exception as e:
        logger.error(f"LLM adapter crashed: {e}. Falling back to template.")
        return generate_template_rationale(contract, style)
