"""
DriftGuard-X v2 — Redaction Tests (3 tests)
"""
from __future__ import annotations

import pytest

from packages.trace_sdk.src.tracer import hash_payload, redact_dict


@pytest.mark.security
def test_sensitive_keys_redacted() -> None:
    """Sensitive field names must be replaced with [REDACTED]."""
    data = {
        "user": "alice",
        "password": "super_secret_123",
        "api_key": "sk-abc123",
        "query": "what is AI?",
    }
    redacted, fields = redact_dict(data)
    assert redacted["user"] == "alice"  # not sensitive
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert "password" in fields
    assert "api_key" in fields


@pytest.mark.security
def test_nested_sensitive_keys_redacted() -> None:
    """Nested sensitive fields are also redacted."""
    data = {
        "user": "alice",
        "auth": {
            "token": "bearer_token_xyz",
            "expires": "2030-01-01",
        },
    }
    redacted, fields = redact_dict(data)
    assert redacted["auth"]["token"] == "[REDACTED]"
    assert redacted["auth"]["expires"] == "2030-01-01"
    assert "auth.token" in fields


@pytest.mark.security
def test_raw_payload_not_stored_only_hash() -> None:
    """hash_payload is deterministic and does not expose original content."""
    payload = {"query": "top secret prompt", "password": "hunter2"}
    h = hash_payload(payload)
    # Hash is 64 hex chars (SHA-256)
    assert len(h) == 64
    assert h.isalnum()
    # Different payload = different hash
    h2 = hash_payload({"query": "different query"})
    assert h != h2
    # Same payload = same hash (deterministic)
    h3 = hash_payload(payload)
    assert h == h3
