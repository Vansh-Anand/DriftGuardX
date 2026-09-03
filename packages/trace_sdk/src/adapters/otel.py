"""
DriftGuard-X v2 — OpenTelemetry Adapter
PRIVATE — All Rights Reserved.

Bridges OpenTelemetry spans to DriftGuard-X TraceContext.
"""

from typing import Any
from uuid import UUID

from opentelemetry.trace import Span as OTSpan

from packages.contracts.src.models import ComponentType, SpanKind
from packages.trace_sdk.src.tracer import TraceContext


class OTelBridge:
    """
    Bridges OpenTelemetry spans to DriftGuard-X internal span representation.
    """

    def __init__(self, trace_ctx: TraceContext):
        self.trace_ctx = trace_ctx

    def sync_span(
        self,
        ot_span: OTSpan,
        component_type: ComponentType,
        version_id: UUID,
        version_tag: str,
        input_payload: Any = None,
        output_payload: Any = None,
    ) -> None:
        """
        Creates a DriftGuard-X span mirroring an active OpenTelemetry span.
        """
        ot_ctx = ot_span.get_span_context()
        span_id_hex = format(ot_ctx.span_id, "016x")

        # We use the internal builder but override the span_id to match OT
        builder = self.trace_ctx.start_span(
            name=ot_span.name or "otel_span", kind=SpanKind.INTERNAL
        )
        builder._span_id = span_id_hex  # Bridge the ID
        builder.set_component(component_type, version_id, version_tag)

        if input_payload is not None:
            builder.set_input(input_payload)
        if output_payload is not None:
            builder.set_output(output_payload)

        builder.finish()
        self.trace_ctx.record_span(builder.build())
