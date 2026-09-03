"""
DriftGuard-X v2 — Deterministic Verifier Contracts
Update 7: Attaching cheap, non-LLM checks to execution traces.
Update 15: Delegated normalization to utils.unicode
"""

from typing import Any

from packages.utils.src.unicode import aggressive_normalize_for_banlist


class DeterministicVerifier:
    """
    Executes cheap deterministic checks against the final output or tool calls
    of a trace to ground evidence in observable constraints rather than
    relying solely on an LLM-as-a-judge.
    """

    @staticmethod
    def verify_tool_calls_present(
        trace_attributes: dict[str, Any], required_tools: list[str]
    ) -> bool:
        """
        Verify that specific tools were invoked in the trace.
        """
        invoked_tools = trace_attributes.get("dgx.tools.invoked", [])
        return all(tool in invoked_tools for tool in required_tools)

    @staticmethod
    def verify_no_forbidden_words(text: str, forbidden_words: list[str]) -> bool:
        """
        Verify that the output does not contain any forbidden words or patterns.
        """
        # Operate on maximally normalized text
        normalized_text = aggressive_normalize_for_banlist(text)

        for word in forbidden_words:
            normalized_word = aggressive_normalize_for_banlist(word)
            if normalized_word in normalized_text:
                return False
        return True

    @staticmethod
    def verify_json_schema(text: str) -> bool:
        """
        Verify that the output is valid JSON (if expected).
        """
        import json

        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    def run_all_contracts(
        self, trace_attributes: dict[str, Any], final_output: str, constraints: dict[str, Any]
    ) -> bool:
        """
        Execute all requested contracts. Fails fast if any fail.
        """
        if "required_tools" in constraints:
            if not self.verify_tool_calls_present(trace_attributes, constraints["required_tools"]):
                return False

        if "forbidden_words" in constraints:
            if not self.verify_no_forbidden_words(final_output, constraints["forbidden_words"]):
                return False

        if constraints.get("require_json", False):
            if not self.verify_json_schema(final_output):
                return False

        return True
