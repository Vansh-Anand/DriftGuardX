"""
DriftGuard-X v2 — OpenTelemetry Exporter

Provides a DriftGuardSpanExporter to natively export OpenTelemetry spans to the DriftGuard-X ingestion endpoint.
"""

from typing import Sequence
import uuid
import datetime

# Attempt to import OTel SDK, but do not fail if not installed (it might be an optional integration)
try:
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.sdk.trace import ReadableSpan
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    
    class SpanExporter:
        pass
        
    class SpanExportResult:
        SUCCESS = 0
        FAILURE = 1
        
    class ReadableSpan:
        pass


from packages.sdk.src.client import DriftGuardClient


class DriftGuardSpanExporter(SpanExporter):
    """
    Exports OpenTelemetry spans to DriftGuard-X via batch_spans.
    """
    
    def __init__(
        self,
        client: DriftGuardClient,
        run_id: str | uuid.UUID,
        tenant_id: str | uuid.UUID,
        pipeline_id: str | uuid.UUID,
    ):
        if not _OTEL_AVAILABLE:
            raise ImportError("opentelemetry-sdk must be installed to use DriftGuardSpanExporter")
        
        self.client = client
        self.run_id = str(run_id)
        self.tenant_id = str(tenant_id)
        self.pipeline_id = str(pipeline_id)

    def export(self, spans: "Sequence[ReadableSpan]") -> "SpanExportResult":
        try:
            payload = []
            for span in spans:
                ctx = span.get_span_context()
                parent = span.parent
                
                # Convert OTel TraceID and SpanID from int to hex
                trace_id_hex = f"{ctx.trace_id:032x}"
                span_id_hex = f"{ctx.span_id:016x}"
                parent_span_id_hex = f"{parent.span_id:016x}" if parent else None
                
                # Best effort status mapping
                status_code = span.status.status_code.name if span.status.status_code else "UNSET"
                
                # Extract attributes
                attributes = dict(span.attributes or {})
                
                payload.append({
                    "trace_id": trace_id_hex,
                    "span_id": span_id_hex,
                    "parent_span_id": parent_span_id_hex,
                    "name": span.name,
                    "kind": span.kind.name if span.kind else "INTERNAL",
                    "start_time": datetime_from_nano(span.start_time).isoformat(),
                    "end_time": datetime_from_nano(span.end_time).isoformat() if span.end_time else None,
                    "status_code": status_code,
                    "attributes": attributes,
                    "run_id": self.run_id,
                    "tenant_id": self.tenant_id,
                    "pipeline_id": self.pipeline_id
                })
            
            if payload:
                self.client.batch_spans(payload)
                
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass


def datetime_from_nano(nanos: int | None):
    if not nanos:
        return None
    return datetime.datetime.fromtimestamp(nanos / 1e9, tz=datetime.timezone.utc)
