"""
DriftGuard-X v2 — Telemetry Fabric Demo

Demonstrates the trace SDK with simulated components.
"""
import asyncio
from uuid import uuid4

from packages.contracts.src.models import ComponentType
from packages.trace_sdk.src.tracer import TraceContext, PrivacyMode
from packages.trace_sdk.src.adapters.agent import AgentInstrumentor

tenant_id = uuid4()
pipeline_id = uuid4()

async def run_simulated_agent():
    print(f"Starting simulated agent run for tenant {tenant_id}")
    run_id = uuid4()
    ctx = TraceContext(tenant_id=tenant_id, pipeline_id=pipeline_id, run_id=run_id)
    instrumentor = AgentInstrumentor(ctx)
    
    # 1. Retrieval Span
    builder = instrumentor.start_span("retrieve_docs", ComponentType.RETRIEVER, str(uuid4()), "v1")
    builder.set_input({"query": "What is the capital of France?"})
    await asyncio.sleep(0.1)
    builder.set_output({"docs": [{"id": "doc1", "content": "Paris is the capital of France."}]})
    builder.set_attribute("dgx.retrieval.top_k", 1)
    # Simulate data residency
    builder.finish(data_residency_label="EU-WEST-1", privacy_mode=PrivacyMode.REDACTED_CONTENT)
    instrumentor.record(builder)
    
    # 2. Tool Call Span (Simulated with PII)
    builder = instrumentor.start_span("fetch_user_data", ComponentType.TOOL_CALL, str(uuid4()), "v1")
    builder.set_input({"user_id": 123})
    await asyncio.sleep(0.05)
    # This PII will be redacted by the SDK when sent to the ingestion service
    builder.set_output({"email": "test.user@example.com", "phone": "555-123-4567"})
    builder.finish(privacy_mode=PrivacyMode.REDACTED_CONTENT)
    instrumentor.record(builder)
    
    # 3. Generator Span
    builder = instrumentor.start_span("generate_response", ComponentType.GENERATOR, str(uuid4()), "v2-exp")
    builder.set_input([
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "system", "content": "Context: Paris is the capital of France. Tool output: [REDACTED]"}
    ])
    await asyncio.sleep(0.2)
    builder.set_output({"content": "The capital of France is Paris."})
    builder.set_tokens(input_tokens=45, output_tokens=7)
    builder.set_attribute("dgx.model.sampling_config", {"temperature": 0.0, "top_p": 1.0})
    builder.finish()
    instrumentor.record(builder)

    print("Agent run complete. Spans generated:")
    for span in ctx.get_spans():
        print(f" - {span.name} ({span.component_type.value if span.component_type else 'internal'}) in {span.latency_ms:.1f}ms")
        if span.redaction:
            print(f"   [Redaction Mode: {span.redaction.privacy_mode.value}]")

if __name__ == "__main__":
    asyncio.run(run_simulated_agent())
