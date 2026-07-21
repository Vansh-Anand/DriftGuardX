import pytest
from packages.replay.src.faults import FaultInjector, get_all_fault_recipes
from packages.replay.src.sandbox import SandboxedWorker, SandboxViolationError, ReplayEngineWithInvariants, InvariantViolationError

def test_18_fault_recipes_exist():
    recipes = get_all_fault_recipes()
    assert len(recipes) >= 18, "Must have at least 18 fault recipes"

def bad_network_call(**kwargs):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("8.8.8.8", 53))
    return True

def test_sandbox_blocks_network():
    with pytest.raises(RuntimeError) as exc_info:
        SandboxedWorker.run(bad_network_call, {})
    
    assert "Sandbox error" in str(exc_info.value)
    assert "Network access blocked" in str(exc_info.value)

def bad_file_write(**kwargs):
    with open("hacked.txt", "w") as f:
        f.write("owned")
    return True

def test_sandbox_blocks_file_write():
    with pytest.raises(RuntimeError) as exc_info:
        SandboxedWorker.run(bad_file_write, {})
    
    assert "Sandbox error" in str(exc_info.value)
    assert "File write blocked" in str(exc_info.value)

def test_freeze_invariant_failure():
    orig_trace = [
        {"span_id": "span1", "component_type": "retriever", "output": {"docs": ["A"]}},
        {"span_id": "span2", "component_type": "generator", "output": {"text": "Hello"}}
    ]
    
    replay_trace = [
        {"span_id": "span1", "component_type": "retriever", "output": {"docs": ["A"]}},
        {"span_id": "span2", "component_type": "generator", "output": {"text": "World"}} # Changed without intervention
    ]
    
    with pytest.raises(InvariantViolationError):
        ReplayEngineWithInvariants.verify_freeze_invariants(
            orig_trace, replay_trace, intervened_component_id="retriever"
        )

def test_freeze_invariant_success():
    orig_trace = [
        {"span_id": "span1", "component_type": "retriever", "output": {"docs": ["A"]}},
        {"span_id": "span2", "component_type": "generator", "output": {"text": "Hello"}}
    ]
    
    replay_trace = [
        {"span_id": "span1", "component_type": "retriever", "output": {"docs": ["B"]}}, # Intervened component changed
        {"span_id": "span2", "component_type": "generator", "output": {"text": "Hello"}}
    ]
    
    ReplayEngineWithInvariants.verify_freeze_invariants(
        orig_trace, replay_trace, intervened_component_id="retriever"
    )
