import pytest
import json
import uuid
from packages.contracts.src.models import TraceArtifact
from packages.contracts.src.registry import VersionRegistry
from packages.graph.src.builder import GraphBuilder
from packages.contracts.src.graph import NodeType, EdgeType

from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_multi_agent_communication_edge():
    registry = AsyncMock()
    builder = GraphBuilder(registry)
    
    # Simulate Agent A (Researcher) making a call, hallucinating, and passing context to Agent B (Executor)
    from datetime import datetime, timezone
    from packages.contracts.src.models import SpanRecord, ComponentType
    
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    
    trace = TraceArtifact(
        tenant_id=tenant_id,
        run_id=run_id,
        pipeline_id=pipeline_id,
        spans=[
            SpanRecord(
                trace_id="12345678901234561234567890123456",
                span_id="1234567890123456",
                tenant_id=tenant_id,
                pipeline_id=pipeline_id,
                run_id=run_id,
                start_time=datetime.now(timezone.utc),
                name="Researcher Agent Output",
                component_type=ComponentType.AGENT,
                attributes={
                    "dgx.agent.message_to": "executor_b"
                }
            ),
            SpanRecord(
                trace_id="12345678901234561234567890123456",
                span_id="1234567890123457",
                parent_span_id="1234567890123456",
                tenant_id=tenant_id,
                pipeline_id=pipeline_id,
                run_id=run_id,
                start_time=datetime.now(timezone.utc),
                name="Executor Agent Receive",
                component_type=ComponentType.AGENT,
                attributes={}
            )
        ]
    )
    
    graph = await builder.build(trace)
    
    # Verify node types
    nodes = {n.id: n for n in graph.nodes}
    assert "event:1234567890123456" in nodes
    assert nodes["event:1234567890123456"].type == NodeType.AGENT
    
    assert "agent:executor_b" in nodes
    assert nodes["agent:executor_b"].type == NodeType.AGENT
    
    # Verify edges
    edges = graph.edges
    
    # There should be an INTER_AGENT_COMMUNICATION edge from span_a_1 to agent:executor_b
    comm_edges = [e for e in edges if e.type == EdgeType.INTER_AGENT_COMMUNICATION]
    assert len(comm_edges) == 1
    assert comm_edges[0].source == "event:1234567890123456"
    assert comm_edges[0].target == "agent:executor_b"
    assert comm_edges[0].label == "messages"
    
    # There should be a CONTROL_FLOW edge from span_a_1 to span_b_1
    control_edges = [e for e in edges if e.type == EdgeType.CONTROL_FLOW]
    assert len(control_edges) == 1
    assert control_edges[0].source == "event:1234567890123456"
    assert control_edges[0].target == "event:1234567890123457"
