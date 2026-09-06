from unittest.mock import MagicMock, patch

import httpx
import pytest

from packages.contracts.src.sdk_models import SpanIngestItem
from packages.sdk.src.client import DriftGuardClient


@pytest.fixture
def sync_client():
    return DriftGuardClient(api_key="test")


def test_batch_spans_success(sync_client):
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id=f"span-{i}",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
        for i in range(3)
    ]

    with patch.object(sync_client.client, "post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"ingested": 3, "skipped": 0, "errors": []}
        mock_post.return_value = mock_response

        result = sync_client.batch_spans(spans)

        assert result.status == "SUCCESS"
        assert result.ingested_count == 3
        assert mock_post.call_count == 1


def test_batch_spans_retryable_5xx(sync_client):
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id="span-1",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
    ]

    with patch.object(sync_client.client, "post") as mock_post, patch("time.sleep") as mock_sleep:

        # Fail twice with 500, then succeed
        error_response = httpx.Response(500, request=httpx.Request("POST", "url"))
        success_response = MagicMock()
        success_response.json.return_value = {"ingested": 1, "skipped": 0, "errors": []}

        mock_post.side_effect = [
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response),
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response),
            success_response,
        ]

        result = sync_client.batch_spans(spans)

        assert result.status == "SUCCESS"
        assert result.ingested_count == 1
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)


def test_batch_spans_permanent_failure(sync_client):
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id="span-1",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
    ]

    with patch.object(sync_client.client, "post") as mock_post, patch("time.sleep"):

        # Fail 3 times with 500
        error_response = httpx.Response(500, request=httpx.Request("POST", "url"))

        mock_post.side_effect = [
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response)
        ] * 3

        result = sync_client.batch_spans(spans)

        assert result.status == "FAILURE"
        assert result.ingested_count == 0
        assert mock_post.call_count == 3
        assert len(result.failed_spans) == 1


def test_batch_spans_non_retryable_4xx(sync_client):
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id="span-1",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
    ]

    with patch.object(sync_client.client, "post") as mock_post, patch("time.sleep") as mock_sleep:

        error_response = httpx.Response(400, request=httpx.Request("POST", "url"))

        mock_post.side_effect = [
            httpx.HTTPStatusError("400", request=error_response.request, response=error_response)
        ]

        result = sync_client.batch_spans(spans)

        assert result.status == "FAILURE"
        assert result.ingested_count == 0
        assert mock_post.call_count == 1  # No retry!
        assert mock_sleep.call_count == 0


def test_batch_spans_multiple_chunks(sync_client):
    sync_client._max_batch_size = 2
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id=f"span-{i}",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
        for i in range(5)
    ]

    with patch.object(sync_client.client, "post") as mock_post:
        success_response_2 = MagicMock()
        success_response_2.json.return_value = {"ingested": 2, "skipped": 0, "errors": []}

        success_response_1 = MagicMock()
        success_response_1.json.return_value = {"ingested": 1, "skipped": 0, "errors": []}

        # 3 chunks: 2, 2, 1
        mock_post.side_effect = [success_response_2, success_response_2, success_response_1]

        result = sync_client.batch_spans(spans)

        assert result.status == "SUCCESS"
        assert result.ingested_count == 5
        assert mock_post.call_count == 3


def test_batch_spans_partial_failure(sync_client):
    sync_client._max_batch_size = 2
    spans = [
        SpanIngestItem(
            trace_id="a",
            span_id=f"span-{i}",
            parent_span_id=None,
            run_id="r1",
            tenant_id="t1",
            pipeline_id="p1",
            name="test",
            kind="INTERNAL",
            start_time="2021-01-01T00:00:00Z",
            attributes={},
        )
        for i in range(4)
    ]

    with patch.object(sync_client.client, "post") as mock_post, patch("time.sleep"):

        success_response = MagicMock()
        success_response.json.return_value = {"ingested": 2, "skipped": 0, "errors": []}

        error_response = httpx.Response(500, request=httpx.Request("POST", "url"))

        # First chunk succeeds, second chunk fails permanently (3 tries)
        mock_post.side_effect = [
            success_response,
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response),
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response),
            httpx.HTTPStatusError("500", request=error_response.request, response=error_response),
        ]

        result = sync_client.batch_spans(spans)

        assert result.status == "PARTIAL_FAILURE"
        assert result.ingested_count == 2
        assert len(result.failed_spans) == 2
        assert mock_post.call_count == 4
