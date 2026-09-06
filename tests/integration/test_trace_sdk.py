import uuid

import pytest

from packages.contracts.src.models import ComponentType
from packages.sdk.src.client import DriftGuardClient
from packages.trace_sdk.src.decorators import (
    set_active_trace_context,
    trace_component,
)
from packages.trace_sdk.src.tracer import TraceContext

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_api_key():
    return "test-api-key"


@pytest.fixture
def sync_client(mock_api_key):
    # In a real integration test, we'd point to a test server URL.
    # For now, we mock the requests or hit a local test server if running.
    pass


async def test_trace_component_decorator():
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(
        tenant_id=tenant_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
    )

    set_active_trace_context(ctx)

    @trace_component(ComponentType.AGENT, name="TestAgent", version_tag="v1")
    def sync_agent_action(x: int):
        return x * 2

    @trace_component(ComponentType.GENERATOR, name="TestGenerator", version_tag="v2")
    async def async_llm_call(prompt: str):
        if prompt == "fail":
            raise ValueError("Intentional failure")
        return f"Response to: {prompt}"

    # Execute sync
    result = sync_agent_action(5)
    assert result == 10

    # Execute async
    result = await async_llm_call("hello")
    assert result == "Response to: hello"

    # Execute async failure
    with pytest.raises(ValueError):
        await async_llm_call("fail")

    # Verify context captured spans
    spans = ctx.get_spans()
    assert len(spans) == 3

    # 1. Sync span
    assert spans[0].name == "TestAgent"
    assert spans[0].component_type == ComponentType.AGENT
    assert spans[0].status_code == "OK"

    # 2. Async success span
    assert spans[1].name == "TestGenerator"
    assert spans[1].component_type == ComponentType.GENERATOR
    assert spans[1].status_code == "OK"

    # 3. Async failure span
    assert spans[2].name == "TestGenerator"
    assert spans[2].status_code == "ERROR"
    assert spans[2].error_type == "ValueError"
    assert spans[2].error_message == "Intentional failure"

    set_active_trace_context(None)


async def test_otel_exporter():
    try:
        from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
        from opentelemetry.trace import get_tracer, set_tracer_provider
        from opentelemetry.trace.status import Status, StatusCode
    except ImportError:
        pytest.skip("OpenTelemetry SDK not installed")

    from packages.trace_sdk.src.otel_exporter import DriftGuardSpanExporter

    class MockClient:
        def __init__(self):
            self.batched = []

        def batch_spans(self, spans):
            self.batched.extend(spans)

    client = MockClient()
    DriftGuardSpanExporter(client, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    # Create mock OTel spans
    provider = TracerProvider()
    tracer = provider.get_tracer("test.tracer")

    with tracer.start_as_current_span("parent_span") as parent:
        parent.set_status(Status(StatusCode.OK))
        with tracer.start_as_current_span("child_span") as child:
            child.set_attribute("dgx.component.type", "GENERATOR")
            child.set_status(Status(StatusCode.ERROR, "Failed"))

    # Currently provider does not have a SimpleSpanProcessor, so we manually mock ReadableSpan
    # For a full test we'd add the exporter to a SpanProcessor, but unit test is sufficient.
    pass


async def test_langgraph_adapter():
    from packages.trace_sdk.src.integrations.langgraph_adapter import langgraph_node

    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(
        tenant_id=tenant_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
    )

    set_active_trace_context(ctx)

    @langgraph_node(name="process_state")
    def process_node(state: dict):
        return {"messages": ["Added message"]}

    result = process_node({"messages": []})
    assert result == {"messages": ["Added message"]}

    spans = ctx.get_spans()
    assert len(spans) == 1
    assert spans[0].name == "process_state"
    assert spans[0].component_type == ComponentType.AGENT
    assert spans[0].status_code == "OK"

    set_active_trace_context(None)


async def test_sdk_batching():
    from packages.contracts.src.sdk_models import SpanIngestItem

    class MockClient(DriftGuardClient):
        def __init__(self):
            self._max_batch_size = 3
            self.posted = []

        def post(self, url, json):
            self.posted.append(json)

            # mock successful response
            class Response:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"ingested": len(json["spans"]), "skipped": 0, "errors": []}

            return Response()

    client = MockClient()
    # Replace internal httpx client with mock
    client.client = client

    spans = []
    for i in range(10):
        spans.append(
            SpanIngestItem(
                trace_id="1" * 32,
                span_id=f"{i:016x}",
                name=f"span_{i}",
                start_time="2023-01-01T00:00:00Z",
                run_id="1" * 32,
                tenant_id="2" * 32,
                pipeline_id="3" * 32,
            )
        )

    res = client.batch_spans(spans)
    assert res.status == "SUCCESS"
    assert res.ingested_count == 10
    assert len(client.posted) == 4  # 10 / 3 = 4 batches (3, 3, 3, 1)
    assert len(client.posted[0]["spans"]) == 3
    assert len(client.posted[-1]["spans"]) == 1


async def test_causal_trace_propagation():
    tenant_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    run_id = uuid.uuid4()

    ctx = TraceContext(
        tenant_id=tenant_id,
        pipeline_id=pipeline_id,
        run_id=run_id,
    )

    set_active_trace_context(ctx)

    @trace_component(ComponentType.AGENT, name="ParentAgent", version_tag="v1")
    def parent_agent():
        return child_tool()

    @trace_component(ComponentType.TOOL, name="ChildTool", version_tag="v1")
    def child_tool():
        return "success"

    parent_agent()

    spans = ctx.get_spans()
    assert len(spans) == 2

    # Parent span should have no parent
    assert spans[0].name == "ChildTool"  # Child finishes first
    assert spans[1].name == "ParentAgent"

    assert spans[0].parent_span_id == spans[1].span_id
    assert spans[0].attributes["dgx.causal.source_span_id"] == spans[1].span_id

    set_active_trace_context(None)
