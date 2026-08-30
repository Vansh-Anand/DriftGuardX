import logging
import re

try:
    from presidio_analyzer import AnalyzerEngine
except ImportError:  # Optional high-recall backend; deterministic regex remains available.
    AnalyzerEngine = None

logger = logging.getLogger(__name__)


class PIISecretScanner:
    def __init__(self):
        self.analyzer = AnalyzerEngine() if AnalyzerEngine is not None else None
        # Basic regex for catching obvious secrets (mock API keys, private keys)
        self.secret_patterns = [
            re.compile(r"(?i)api[_-]?key[\s=:A-Z0-9]+"),
            re.compile(r"-----BEGIN PRIVATE KEY-----"),
            re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
            re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
        ]

    def scan_text(self, text: str) -> bool:
        """
        Scans text for PII or secrets.
        Returns False if text is SAFE.
        Returns True if text contains PII or secrets (UNSAFE).
        """
        if not text:
            return False

        # 1. Presidio PII check
        results = (
            self.analyzer.analyze(
                text=text,
                entities=["PHONE_NUMBER", "CREDIT_CARD", "EMAIL_ADDRESS", "US_SSN", "CRYPTO"],
                language="en",
            )
            if self.analyzer is not None
            else []
        )
        if results:
            logger.warning(f"PII Scanner caught potential PII: {[r.entity_type for r in results]}")
            return True

        # 2. Regex Secret check
        for pattern in self.secret_patterns:
            if pattern.search(text):
                logger.warning(
                    f"Secret Scanner caught potential secret matching: {pattern.pattern}"
                )
                return True

        return False
