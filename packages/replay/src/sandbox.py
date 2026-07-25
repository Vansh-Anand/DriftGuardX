"""
DriftGuard-X v2 — Sandboxed Do-Operator Replay
PRIVATE — All Rights Reserved.
"""
import multiprocessing
import sys
from typing import Any, Callable, Dict
import hashlib
import json
import threading

# We use thread-local storage to track the current trace_id during sandbox execution
sandbox_local = threading.local()

class SandboxViolationError(Exception):
    pass

class InvariantViolationError(Exception):
    pass

# We use thread-local storage to track the current trace_id during sandbox execution
sandbox_local = threading.local()

def _sandbox_audit_hook(event: str, args: tuple):
    """
    Python audit hook to aggressively block network and specific filesystem operations.
    Now upgraded to stage intercepted actions via the VTI Coordinator.
    """
    trace_id = getattr(sandbox_local, "trace_id", "unknown_trace")
    if not hasattr(sandbox_local, "staged_actions"):
        sandbox_local.staged_actions = []
    
    if event == "socket.connect" or event == "socket.bind":
        sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "NETWORK_CALL", "payload": {"event": event, "args": str(args)}})
        raise SandboxViolationError(f"Network access staged and blocked in sandbox: {event} {args}")
        
    if event == "open":
        filename, mode, *rest = args
        # Block write/append modes unless it's a known fixture
        if isinstance(mode, str) and any(m in mode for m in ('w', 'a', 'x', '+')):
            # Allowlist /dev/null or specific temp files if needed
            if "fixture" not in str(filename):
                sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "FILE_WRITE", "payload": {"filename": str(filename), "mode": mode}})
                raise SandboxViolationError(f"File write staged and blocked in sandbox: {filename}")
                
    if event.startswith("subprocess.") or event == "os.system":
        sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "SHELL_EXEC", "payload": {"event": event, "command": str(args)}})
        raise SandboxViolationError(f"Shell execution staged and blocked in sandbox: {event}")


def _sandboxed_execution_wrapper(func: Callable, inputs: Dict[str, Any], return_dict: dict, trace_id: str):
    """
    Runs inside the multiprocessing subprocess.
    """
    try:
        from packages.replay.src.arc_isolator import arc_isolator
        
        sandbox_local.trace_id = trace_id
        sandbox_local.staged_actions = []
        sys.addaudithook(_sandbox_audit_hook)
        
        arc_isolator.enable()
        try:
            result = func(**inputs)
        finally:
            arc_isolator.disable()
            
        return_dict['result'] = result
        return_dict['staged_actions'] = sandbox_local.staged_actions
    except Exception as e:
        return_dict['error'] = str(e)
        return_dict['staged_actions'] = getattr(sandbox_local, "staged_actions", [])


class SandboxedWorker:
    """
    Executes a function in a tightly restricted multiprocessing boundary.
    """
    @staticmethod
    def run(func: Callable, inputs: Dict[str, Any], timeout_seconds: int = 5, trace_id: str = "default") -> Dict[str, Any]:
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        
        p = multiprocessing.Process(
            target=_sandboxed_execution_wrapper,
            args=(func, inputs, return_dict, trace_id)
        )
        p.start()
        p.join(timeout=timeout_seconds)
        
        if p.is_alive():
            p.terminate()
            p.join()
            raise TimeoutError("Sandboxed execution timed out.")
            
        from packages.replay.src.vti_coordinator import vti_coordinator
        for action in return_dict.get('staged_actions', []):
            vti_coordinator.stage_action(action["trace_id"], action["type"], action["payload"])
            
        if 'error' in return_dict:
            raise RuntimeError(f"Sandbox error: {return_dict['error']}")
            
        return return_dict.get('result')


class ReplayEngineWithInvariants:
    """
    Do-operator replay engine that freezes non-intervened components and verifies hashes.
    """
    
    @staticmethod
    def verify_freeze_invariants(original_trace: list, replay_trace: list, intervened_component_id: str):
        """
        Verify that all non-intervened components produced the exact same output hashes.
        """
        orig_map = {s['span_id']: s for s in original_trace}
        replay_map = {s['span_id']: s for s in replay_trace}
        
        for span_id, orig_span in orig_map.items():
            if orig_span.get('component_type') == intervened_component_id:
                continue
                
            if span_id not in replay_map:
                continue
                
            replay_span = replay_map[span_id]
            
            orig_out = json.dumps(orig_span.get('output', {}), sort_keys=True).encode()
            replay_out = json.dumps(replay_span.get('output', {}), sort_keys=True).encode()
            
            if hashlib.md5(orig_out).hexdigest() != hashlib.md5(replay_out).hexdigest():
                raise InvariantViolationError(
                    f"Freeze invariant violated! Component {span_id} output changed during replay despite not being intervened."
                )
