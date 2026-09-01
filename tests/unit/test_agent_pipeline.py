import uuid
from packages.rag_pipeline.src.agents import AgentPipeline

def test_agent_pipeline_execution():
    pipeline = AgentPipeline()
    run_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    
    state = pipeline.run("Is the system healthy?", run_id, tenant_id)
    
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
        "response"
    ]
