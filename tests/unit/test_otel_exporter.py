import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from opentelemetry.sdk.trace.export import SpanExportResult
from packages.trace_sdk.src.otel_exporter import DriftGuardSpanExporter, datetime_from_nano
from packages.contracts.src.sdk_models import BatchResult

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.fixture
def exporter(mock_client):
    return DriftGuardSpanExporter(
        client=mock_client,
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        pipeline_id=uuid.uuid4()
    )

@pytest.fixture
def mock_span():
    span = MagicMock()
    span.get_span_context.return_value.trace_id = 1
    span.get_span_context.return_value.span_id = 2
    span.parent = None
    span.name = "test_span"
    span.kind.name = "INTERNAL"
    span.start_time = 1609459200000000000
    span.end_time = 1609459201000000000
    span.status.status_code.name = "OK"
    span.attributes = {}
    return span

def test_export_success(exporter, mock_client, mock_span):
    mock_client.batch_spans.return_value = BatchResult(
        status="SUCCESS",
        ingested_count=1,
        skipped_count=0,
        failed_spans=[],
        errors=[]
    )
    
    result = exporter.export([mock_span])
    assert result == SpanExportResult.SUCCESS

def test_export_partial_failure(exporter, mock_client, mock_span):
    mock_client.batch_spans.return_value = BatchResult(
        status="PARTIAL_FAILURE",
        ingested_count=1,
        skipped_count=0,
        failed_spans=["failed_span"],
        errors=["Some error"]
    )
    
    result = exporter.export([mock_span])
    assert result == SpanExportResult.FAILURE

def test_export_complete_failure(exporter, mock_client, mock_span):
    mock_client.batch_spans.return_value = BatchResult(
        status="FAILURE",
        ingested_count=0,
        skipped_count=0,
        failed_spans=["span1"],
        errors=["Network error"]
    )
    
    result = exporter.export([mock_span])
    assert result == SpanExportResult.FAILURE

def test_export_exception(exporter, mock_client, mock_span):
    mock_client.batch_spans.side_effect = Exception("Crash")
    
    result = exporter.export([mock_span])
    assert result == SpanExportResult.FAILURE

def test_force_flush(exporter):
    assert exporter.force_flush() is True
    exporter.shutdown()
    assert exporter.force_flush() is False

def test_shutdown_idempotent(exporter):
    exporter.shutdown()
    assert exporter._is_shutdown is True
    # Should not raise
    exporter.shutdown()

def test_export_after_shutdown(exporter, mock_client, mock_span):
    exporter.shutdown()
    result = exporter.export([mock_span])
    assert result == SpanExportResult.FAILURE
    assert mock_client.batch_spans.call_count == 0
