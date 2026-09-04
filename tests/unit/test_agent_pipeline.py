import uuid

from packages.rag_pipeline.src.agents import AgentPipeline
from packages.trace_sdk.src.tracer import TraceContext


def test_agent_pipeline_execution():
    pipeline = AgentPipeline()
    run_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    pipeline_id = uuid.uuid4()
    
    trace_ctx = TraceContext(
        tenant_id=uuid.UUID(tenant_id),
        pipeline_id=pipeline_id,
        run_id=uuid.UUID(run_id)
    )

    state = pipeline.run("Is the system healthy?", run_id, tenant_id, trace_ctx=trace_ctx)

    assert state.is_finished is True
    assert state.final_response == "The system is healthy and verified."
    assert len(state.invocations) == 7

    agents_executed = [inv.agent_name for inv in state.invocations]
    assert agents_executed == [
        "orchestrator",
        "retrieval",
        "reasoning",
        "tool",
        "verifier",
        "policy",
        "response",
    ]

    spans = trace_ctx.get_spans()
    
    # 7 agents + multiple memory ops. 
    # memory writes: retrieved_docs, reasoning, tool_results, verified, policy_decision
    # memory reads: retrieved_docs
    assert len(spans) > 7
    
    # Check that agent spans have stable identity fields
    agent_spans = [s for s in spans if s.name in agents_executed]
    assert len(agent_spans) == 7
    
    for span in agent_spans:
        assert "dgx.agent.id" in span.attributes
        assert "dgx.agent.type" in span.attributes
        assert span.attributes["dgx.agent.version"] == "v1.0"
        
    # Check causal relationships
    # The first agent (orchestrator) has no source span, but the second (retrieval) should have the first as its source.
    assert "dgx.causal.source_span_id" not in agent_spans[0].attributes
    assert agent_spans[1].attributes["dgx.causal.source_span_id"] == agent_spans[0].span_id
    
    # Check memory spans
    memory_spans = [s for s in spans if s.name in ("memory_read", "memory_write")]
    assert len(memory_spans) >= 6
    
    # Check policy decision span
    policy_span = next(s for s in agent_spans if s.name == "policy")
    assert policy_span.attributes.get("dgx.decision.outcome") == "allow"
    assert policy_span.attributes.get("dgx.evidence.classification") == "synthetic_simulation"


def test_agent_pipeline_with_real_components():
    from unittest.mock import AsyncMock
    from packages.rag_pipeline.src.adapters.postgres_retriever import PgRetrievedChunk
    from packages.rag_pipeline.src.tool_registry import ToolRegistry

    mock_retriever = AsyncMock()
    mock_retriever.retrieve.return_value = [
        PgRetrievedChunk("chunk-101", "Real database chunk on cluster status.", 0.98, "doc-101")
    ]

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        "text": "Cluster status is fully operational and healthy.",
        "tokens_input": 20,
        "tokens_output": 10,
        "latency_ms": 50.0,
        "cost_usd": 0.0001,
        "model_metadata": {"model": "gpt-4o", "provider": "openai"},
    }

    tools = ToolRegistry()
    pipeline = AgentPipeline(retriever=mock_retriever, llm=mock_llm, tool_registry=tools)

    run_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    trace_ctx = TraceContext(
        tenant_id=uuid.UUID(tenant_id),
        pipeline_id=uuid.uuid4(),
        run_id=uuid.UUID(run_id),
    )

    state = pipeline.run("Check cluster health and calculate metrics", run_id, tenant_id, trace_ctx=trace_ctx)

    assert state.is_finished is True
    assert state.read_memory("verified") is True
    assert "healthy" in state.final_response.lower()
    assert len(state.invocations) == 7
