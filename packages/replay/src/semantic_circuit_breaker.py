"""
DriftGuard-X v2 — Semantic Circuit Breaker
Network I/O Optimization: Parses the agent's intent AST *before* execution to detect
state-mutating operations (UPDATE, DELETE, INSERT, POST) and trips the circuit
immediately, bypassing the entire HTTP serialization / network stack.

Patent Claim: Reduces network I/O overhead and CPU serialization latency by
pre-empting destructive network calls at the semantic intent layer rather than
at the socket boundary.

PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import ast
import re
from enum import Enum
from typing import Any


class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation — all calls allowed
    TRIPPED = "TRIPPED"  # State-mutating intent detected — bypass active


# Patterns that signal state-mutating intent in code / SQL / HTTP verbs
_MUTATING_KEYWORDS: list[str] = [
    # SQL
    "UPDATE",
    "DELETE",
    "INSERT",
    "DROP",
    "TRUNCATE",
    "ALTER",
    # HTTP verbs (common string literals agents emit)
    "POST",
    "PUT",
    "PATCH",
    # Common agent tool-call patterns
    "send_email",
    "write_file",
    "execute_sql",
    "publish",
    "commit",
]

_MUTATING_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _MUTATING_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


class SemanticCircuitBreaker:
    """
    Inspects an agent's code snippet or tool-call description at the AST /
    keyword level before execution.  If mutating intent is detected, the
    circuit is tripped and the call is bypassed instantly — before any bytes
    are serialized or sent over the network.
    """

    def __init__(self, mock_payload: dict[str, Any] | None = None):
        """
        Args:
            mock_payload: Synthetic response fed back through the loopback
                          channel when the circuit is tripped.
        """
        self.state = CircuitState.CLOSED
        self._mock_payload = mock_payload or {
            "status": 200,
            "body": {"mock": "semantic_circuit_breaker_loopback"},
            "headers": {"X-DriftGuardX-Intercepted": "true"},
        }
        self.trip_log: list[dict[str, Any]] = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _detect_via_keywords(self, code_or_description: str) -> str | None:
        """Return the first mutating keyword found, or None."""
        m = _MUTATING_PATTERN.search(code_or_description)
        return m.group(0).upper() if m else None

    def _detect_via_ast(self, source: str) -> str | None:
        """
        Walk the Python AST looking for function calls or attribute accesses
        whose names imply state mutation (e.g., requests.post, db.delete).
        Returns the suspicious call name, or None if source is not valid Python.
        """
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError:
            return None  # Not Python — fall back to keyword scan

        for node in ast.walk(tree):
            # Catch direct function calls like delete(...), update(...)
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name and _MUTATING_PATTERN.match(name):
                    return name.upper()
        return None

    # ── Public API ────────────────────────────────────────────────────────────

    def inspect(self, code_or_description: str) -> bool:
        """
        Inspect an agent code snippet or tool description.

        Returns:
            True  if mutating intent is detected (circuit tripped).
            False if the call is safe to proceed (circuit closed).
        """
        # Fast keyword scan first (O(N) regex — very cheap)
        trigger = self._detect_via_keywords(code_or_description)

        # If no keyword hit, try AST scan for valid Python
        if trigger is None:
            trigger = self._detect_via_ast(code_or_description)

        if trigger:
            self.state = CircuitState.TRIPPED
            self.trip_log.append(
                {
                    "trigger": trigger,
                    "snippet": code_or_description[:200],
                }
            )
            return True  # Mutating intent detected — trip!

        self.state = CircuitState.CLOSED
        return False

    def execute_with_breaker(
        self, code_or_description: str, live_callable, *args, **kwargs
    ) -> dict[str, Any]:
        """
        Main execution gateway.  If mutating intent is found, bypass the live
        callable entirely and return the synthetic loopback payload.

        Args:
            code_or_description: The agent's intent string / source code.
            live_callable:       The actual function that would execute the call.

        Returns:
            Either the live result or the mock loopback payload.
        """
        if self.inspect(code_or_description):
            # Circuit tripped — return synthetic loopback instantly.
            # Zero bytes sent over the network.
            return {"intercepted": True, **self._mock_payload}

        # Safe — execute the real callable
        result = live_callable(*args, **kwargs)
        return {"intercepted": False, "result": result}

    def reset(self) -> None:
        """Reset circuit to CLOSED state (for testing)."""
        self.state = CircuitState.CLOSED
