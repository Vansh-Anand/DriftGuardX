"""
DriftGuard-X v2 — Trace SDK

OpenTelemetry-compatible tracing with DriftGuard-X extensions.
Provides span building, input/output hashing, and redaction utilities.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from packages.contracts.src.models import (
    ComponentType,
    PrivacyMode,
    RedactionMetadata,
    SpanKind,
    SpanRecord,
)

# ─── Redaction ────────────────────────────────────────────────────────────────

# Fields that must never be stored in plaintext
_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "credit_card",
        "ssn",
        "private_key",
        "access_key",
        "prompt",
        "completion",
        "raw_query",
        "pii",
    }
)

_REDACTED_PLACEHOLDER = "[REDACTED]"
_ENABLE_REDACTION = os.environ.get("ENABLE_REDACTION", "true").lower() == "true"


import re

# Basic PII regex patterns for detection
_PII_PATTERNS = {
    "email": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
}

def redact_dict(data: dict[str, Any], *, force: bool = False, allowlist: list[str] | None = None, privacy_mode: PrivacyMode = PrivacyMode.REDACTED_CONTENT) -> tuple[dict[str, Any], list[str]]:
    """
    Recursively redact sensitive keys and PII patterns from a dict.
    Returns (redacted_dict, list_of_redacted_field_paths).
    """
    if not (_ENABLE_REDACTION or force):
        return data, []

    redacted_fields: list[str] = []

    def _redact(obj: Any, path: str = "") -> Any:
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                field_path = f"{path}.{k}" if path else k

                # Check allowlist
                if allowlist and any(field_path == allowed or field_path.startswith(f"{allowed}.") for allowed in allowlist):
                    result[k] = _redact(v, field_path)
                    continue

                if k.lower() in _SENSITIVE_FIELD_NAMES or privacy_mode == PrivacyMode.METADATA_ONLY:
                    result[k] = _REDACTED_PLACEHOLDER
                    redacted_fields.append(field_path)
                else:
                    if isinstance(v, str):
                        original_v = v
                        for pii_type, pattern in _PII_PATTERNS.items():
                            if pattern.search(v):
                                v = pattern.sub(f"[{pii_type.upper()}_REDACTED]", v)
                        if v != original_v:
                            redacted_fields.append(field_path)
                        result[k] = v
                    else:
                        result[k] = _redact(v, field_path)
            return result
        elif isinstance(obj, list):
            return [_redact(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        return obj

    return _redact(data), redacted_fields


# ─── Hashing ──────────────────────────────────────────────────────────────────

def hash_payload(payload: Any) -> str:
    """
    Compute a deterministic SHA-256 hash of any serializable payload.
    This is what gets stored instead of raw inputs/outputs.
    """
    if isinstance(payload, (dict, list)):
        serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    elif isinstance(payload, str):
        serialized = payload.encode()
    elif isinstance(payload, bytes):
        serialized = payload
    else:
        serialized = str(payload).encode()
    return hashlib.sha256(serialized).hexdigest()


def hash_config(config: dict[str, Any]) -> str:
    """Hash a component configuration dict."""
    return hash_payload(config)


# ─── ID Generation ────────────────────────────────────────────────────────────

def new_trace_id() -> str:
    """Generate a 128-bit (32 hex char) trace ID."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """Generate a 64-bit (16 hex char) span ID."""
    return secrets.token_hex(8)


# ─── Span Builder ─────────────────────────────────────────────────────────────

class SpanBuilder:
    """
    Builds a SpanRecord step by step.
    Usage:
        builder = SpanBuilder(trace_id=..., tenant_id=..., pipeline_id=..., run_id=...)
        builder.set_component(ComponentType.RETRIEVER, version_id=..., version_tag="v1")
        builder.set_input({"query": "..."})
        builder.set_output({"documents": [...]})
        span = builder.build()
    """

    def __init__(
        self,
        *,
        trace_id: str,
        tenant_id: UUID,
        pipeline_id: UUID,
        run_id: UUID,
        name: str = "",
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: str | None = None,
    ) -> None:
        self._trace_id = trace_id
        self._span_id = new_span_id()
        self._tenant_id = tenant_id
        self._pipeline_id = pipeline_id
        self._run_id = run_id
        self._name = name
        self._kind = kind
        self._parent_span_id = parent_span_id
        self._start_time = datetime.now(UTC)
        self._end_time: datetime | None = None
        self._component_type: ComponentType | None = None
        self._component_version_id: UUID | None = None
        self._component_version_tag: str | None = None
        self._input_hash: str | None = None
        self._output_hash: str | None = None
        self._attributes: dict[str, Any] = {}
        self._token_count_input: int | None = None
        self._token_count_output: int | None = None
        self._cost_usd: float | None = None
        self._policy_result: str | None = None
        self._policy_rule_id: str | None = None
        self._error_type: str | None = None
        self._error_message: str | None = None
        self._redaction: RedactionMetadata | None = None
        self._status_code = "UNSET"
        self._status_message = ""
        self._latency_ms: float | None = None

    @property
    def span_id(self) -> str:
        return self._span_id

    def set_component(
        self,
        component_type: ComponentType,
        version_id: UUID,
        version_tag: str,
    ) -> SpanBuilder:
        self._component_type = component_type
        self._component_version_id = version_id
        self._component_version_tag = version_tag
        if not self._name:
            self._name = f"{component_type.value}/{version_tag}"
        return self

    def set_input(self, payload: Any) -> SpanBuilder:
        """Hash the input; do not store raw payload."""
        self._input_hash = hash_payload(payload)
        return self

    def set_output(self, payload: Any) -> SpanBuilder:
        """Hash the output; do not store raw payload."""
        self._output_hash = hash_payload(payload)
        return self

    def set_tokens(self, input_tokens: int, output_tokens: int) -> SpanBuilder:
        self._token_count_input = input_tokens
        self._token_count_output = output_tokens
        return self

    def set_cost(self, cost_usd: float) -> SpanBuilder:
        self._cost_usd = cost_usd
        return self

    def set_policy(self, result: str, rule_id: str | None = None) -> SpanBuilder:
        self._policy_result = result
        self._policy_rule_id = rule_id
        return self

    def set_error(self, error_type: str, message: str) -> SpanBuilder:
        self._error_type = error_type
        self._error_message = message
        self._status_code = "ERROR"
        self._status_message = message
        return self

    def set_attribute(self, key: str, value: Any) -> SpanBuilder:
        self._attributes[key] = value
        return self

    def finish(self, allowlist: list[str] | None = None, privacy_mode: PrivacyMode = PrivacyMode.DEVELOPMENT_FULL, data_residency_label: str | None = None) -> SpanBuilder:
        """Mark the span as finished and compute latency."""
        self._end_time = datetime.now(UTC)
        self._latency_ms = (
            (self._end_time - self._start_time).total_seconds() * 1000
        )
        if self._status_code == "UNSET":
            self._status_code = "OK"

        # Ensure RedactionMetadata is updated if needed
        if allowlist or data_residency_label or privacy_mode != PrivacyMode.DEVELOPMENT_FULL:
            if not self._redaction:
                self._redaction = RedactionMetadata(privacy_mode=privacy_mode)
            if allowlist:
                self._redaction.allowlist_applied = allowlist
            if data_residency_label:
                self._redaction.data_residency_label = data_residency_label
            if privacy_mode:
                self._redaction.privacy_mode = privacy_mode

        return self

    def build(self) -> SpanRecord:
        return SpanRecord(
            trace_id=self._trace_id,
            span_id=self._span_id,
            parent_span_id=self._parent_span_id,
            name=self._name or "unnamed",
            kind=self._kind,
            start_time=self._start_time,
            end_time=self._end_time,
            status_code=self._status_code,
            status_message=self._status_message,
            attributes=self._attributes,
            tenant_id=self._tenant_id,
            pipeline_id=self._pipeline_id,
            run_id=self._run_id,
            component_type=self._component_type,
            component_version_id=self._component_version_id,
            component_version_tag=self._component_version_tag,
            input_hash=self._input_hash,
            output_hash=self._output_hash,
            latency_ms=self._latency_ms,
            token_count_input=self._token_count_input,
            token_count_output=self._token_count_output,
            cost_usd=self._cost_usd,
            policy_result=self._policy_result,
            policy_rule_id=self._policy_rule_id,
            error_type=self._error_type,
            error_message=self._error_message,
            redaction=self._redaction,
        )


# ─── Trace Context ────────────────────────────────────────────────────────────

class TraceContext:
    """
    Manages trace/span context for a single pipeline execution.
    Not thread-safe — create one per request.
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        pipeline_id: UUID,
        run_id: UUID,
        trace_id: str | None = None,
    ) -> None:
        self.trace_id = trace_id or new_trace_id()
        self.tenant_id = tenant_id
        self.pipeline_id = pipeline_id
        self.run_id = run_id
        self._spans: list[SpanRecord] = []
        self._current_span_id: str | None = None

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: str | None = None,
    ) -> SpanBuilder:
        builder = SpanBuilder(
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            pipeline_id=self.pipeline_id,
            run_id=self.run_id,
            name=name,
            kind=kind,
            parent_span_id=parent_span_id or self._current_span_id,
        )
        return builder

    def record_span(self, span: SpanRecord) -> None:
        self._spans.append(span)
        self._current_span_id = span.span_id

    def get_spans(self) -> list[SpanRecord]:
        return list(self._spans)
