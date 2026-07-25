import pytest
import time
from packages.replay.src.aor_scheduler import AORScheduler, AORTask, TaskStatus

def root_agent():
    time.sleep(0.1)
    return "root_success"

def failing_agent():
    # Fails immediately
    raise ValueError("Agent crashed due to drift!")

def dependent_agent():
    # Should not be executed
    return "dependent_success"

def independent_agent():
    # Takes some time to ensure it runs concurrently
    time.sleep(0.2)
    return "independent_success"

def test_aor_scheduler_reallocation_and_diagnostic():
    scheduler = AORScheduler(max_workers=4)
    
    # 1. Root Agent
    t_root = AORTask("root", root_agent, {})
    # 2. Failing Agent (Depends on root)
    t_failing = AORTask("failing", failing_agent, {}, dependencies=["root"])
    # 3. Dependent Agent (Depends on failing)
    t_dependent = AORTask("dependent", dependent_agent, {}, dependencies=["failing"])
    # 4. Independent Agent (Depends on root, runs in parallel with failing)
    t_independent = AORTask("independent", independent_agent, {}, dependencies=["root"])
    
    scheduler.add_task(t_root)
    scheduler.add_task(t_failing)
    scheduler.add_task(t_dependent)
    scheduler.add_task(t_independent)
    
    scheduler.run()
    scheduler.shutdown()
    
    # Verify Root
    assert t_root.status == TaskStatus.COMPLETED
    assert t_root.result == "root_success"
    
    # Verify Failing Agent -> Failed and then Diagnosed
    # The run() loop waits until it finishes diagnosing as well
    # Wait, `run()` waits until there are no PENDING, RUNNING, or DIAGNOSING tasks
    assert t_failing.status == TaskStatus.DIAGNOSING or t_failing.status == TaskStatus.FAILED
    assert isinstance(t_failing.error, ValueError)
    
    # Ensure diagnostic result is recorded from the VTI sandbox
    # SandboxedWorker will catch the error and return it in the dict
    assert t_failing.diagnostic_result is not None
    assert "error" in t_failing.diagnostic_result or "error" in t_failing.diagnostic_result.get("error", "")
    
    # Verify Dependent Agent -> Blocked
    assert t_dependent.status == TaskStatus.BLOCKED
    
    # Verify Independent Agent -> Completed despite sibling failure
    assert t_independent.status == TaskStatus.COMPLETED
    assert t_independent.result == "independent_success"
