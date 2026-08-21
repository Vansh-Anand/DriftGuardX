"""
DriftGuard-X v2 — Deterministic Verifier Contracts
Update 7: Attaching cheap, non-LLM checks to execution traces.
"""
import re
import unicodedata
import urllib.parse
import html
from typing import Dict, Any, List

class DeterministicVerifier:
    """
    Executes cheap deterministic checks against the final output or tool calls
    of a trace to ground evidence in observable constraints rather than
    relying solely on an LLM-as-a-judge.
    """
    
    @staticmethod
    def verify_tool_calls_present(trace_attributes: Dict[str, Any], required_tools: List[str]) -> bool:
        """
        Verify that specific tools were invoked in the trace.
        """
        invoked_tools = trace_attributes.get("dgx.tools.invoked", [])
        for tool in required_tools:
            if tool not in invoked_tools:
                return False
        return True
        
    @staticmethod
    def _normalize_text(text: str, max_decode_passes: int = 3, max_length: int = 500_000) -> str:
        """
        Normalizes text to prevent bypass via homoglyphs, zero-width chars, or odd spaces.
        Bounds decoding and length to prevent DoS attacks.
        """
        if not text:
            return ""
            
        # 1. Length Bound (Prevent DoS)
        if len(text) > max_length:
            text = text[:max_length]
            
        # 2. Bounded Decoding
        decoded = text
        for _ in range(max_decode_passes):
            prev = decoded
            decoded = urllib.parse.unquote(decoded)
            decoded = html.unescape(decoded)
            if prev == decoded:
                break
                
        # 3. Unicode Normalization & Case Folding
        # NFKC normalizes compatibility characters (e.g., fullwidth chars)
        normalized = unicodedata.normalize('NFKC', decoded).casefold()
        
        # 3.5 Homoglyph Mapping
        # Map common Cyrillic/Greek characters that look like Latin characters
        homoglyphs = str.maketrans("асеорхуі", "aceopxyi")
        normalized = normalized.translate(homoglyphs)
        
        # 4. Strip Zero-Width and Control Characters
        # Removes zero-width spaces, joiners, non-joiners, BOM, etc.
        normalized = re.sub(r'[\u200b\u200c\u200d\uFEFF]', '', normalized)
        
        # 5. Collapse Whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 6. Remove all punctuation (to defeat 'b.a.d.w.o.r.d' or 'b,a,d,w,o,r,d')
        # We only keep alphanumeric and single spaces. \w includes underscore, so we replace underscore as well.
        normalized = re.sub(r'[^\w\s]|_', '', normalized)
        
        # 7. Collapse spaces again (in case punctuation removal created double spaces)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # 8. Remove internal spaces entirely for the final check to defeat 'b a d w o r d'
        # Wait, removing all spaces means we just have a giant string of letters.
        # This makes substring search robust against spacing attacks.
        normalized = normalized.replace(" ", "")
        
        return normalized

    @staticmethod
    def verify_no_forbidden_words(text: str, forbidden_words: List[str]) -> bool:
        """
        Verify that the output does not contain any forbidden words or patterns.
        """
        # Save original for audit, operate on normalized
        normalized_text = DeterministicVerifier._normalize_text(text)
        
        for word in forbidden_words:
            normalized_word = DeterministicVerifier._normalize_text(word)
            # Since we removed all spaces and punctuation, we just do a substring search.
            # This is safer against spacer attacks.
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

    @staticmethod
    def verify_arithmetic_consistency(text: str) -> bool:
        """
        A placeholder for a check that extracts equations from text and verifies them.
        """
        # E.g. find "X + Y = Z" and verify.
        return True

    def run_all_contracts(self, trace_attributes: Dict[str, Any], final_output: str, constraints: Dict[str, Any]) -> bool:
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
