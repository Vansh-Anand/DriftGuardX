"""
DriftGuard-X v2 — Sandboxed Do-Operator Replay
Update 14: Atomic execution budget and multiprocessing OS limits.
PRIVATE — All Rights Reserved.
"""
import hashlib
import json
import multiprocessing
import os
import sys
import threading
from collections.abc import Callable
from typing import Any

# Platform specific resource bounds
try:
    import resource
    HAS_RESOURCE_LIMITS = True
except ImportError:
    HAS_RESOURCE_LIMITS = False

sandbox_local = threading.local()

class SandboxViolationError(Exception):
    pass

class InvariantViolationError(Exception):
    pass

class ExecutionBudgetExceeded(Exception):
    pass

class AtomicExecutionBudget:
    """
    Atomic budget reservation for memory, cpu, and network calls.
    Must reserve upfront.
    """
    def __init__(self, max_memory_mb: int = 512, max_cpu_seconds: int = 10, max_network_calls: int = 0):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_seconds = max_cpu_seconds
        self.max_network_calls = max_network_calls
        self._lock = threading.Lock()
        self.network_calls_used = 0

    def reserve_network_call(self):
        with self._lock:
            if self.network_calls_used >= self.max_network_calls:
                raise ExecutionBudgetExceeded(f"Network call budget exceeded ({self.max_network_calls}).")
            self.network_calls_used += 1

def _sandbox_audit_hook(event: str, args: tuple):
    trace_id = getattr(sandbox_local, "trace_id", "unknown_trace")
    if not hasattr(sandbox_local, "staged_actions"):
        sandbox_local.staged_actions = []
    budget = getattr(sandbox_local, "budget", None)

    if event.startswith("socket."):
        if budget:
            budget.reserve_network_call()
        sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "NETWORK_CALL", "payload": {"event": event, "args": str(args)}})
        raise SandboxViolationError(f"Network access staged and blocked in sandbox: {event} {args}")

    if event == "open":
        filename, mode, *rest = args
        if isinstance(mode, str):
            if any(m in mode for m in ('w', 'a', 'x', '+')):
                if "fixture" not in str(filename):
                    sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "FILE_WRITE", "payload": {"filename": str(filename), "mode": mode}})
                    raise SandboxViolationError(f"File write staged and blocked in sandbox: {filename}")
            elif 'r' in mode:
                abs_path = os.path.abspath(str(filename))
                allowed_dir = os.path.abspath(os.getcwd())
                if not abs_path.startswith(allowed_dir):
                    raise SandboxViolationError(f"File read outside allowed directory blocked in sandbox: {filename}")

    if event.startswith("subprocess.") or event == "os.system":
        sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "SHELL_EXEC", "payload": {"event": event, "command": str(args)}})
        raise SandboxViolationError(f"Shell execution staged and blocked in sandbox: {event}")

    if event == "os.kill":
        raise SandboxViolationError("Process signaling (os.kill) blocked in sandbox.")

def _apply_os_limits(memory_mb: int, cpu_seconds: int):
    """Apply strict OS resource limits where available (Linux/Unix)."""
    if HAS_RESOURCE_LIMITS:
        # Limit address space
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        # Limit CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        # Limit subprocesses
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    else:
        # Warning printed for audit logs
        print("WARNING: OS resource limits (RLIMIT) unavailable on this platform. Falling back to multiprocessing timeouts.")

def _sandboxed_execution_wrapper(func: Callable, inputs: dict[str, Any], return_dict: dict, trace_id: str, enable_arc: bool = True, memory_mb: int = 512, cpu_seconds: int = 10):
    try:
        from packages.replay.src.arc_isolator import arc_isolator

        _apply_os_limits(memory_mb, cpu_seconds)

        sandbox_local.trace_id = trace_id
        sandbox_local.staged_actions = []
        sandbox_local.budget = AtomicExecutionBudget(max_memory_mb=memory_mb, max_cpu_seconds=cpu_seconds, max_network_calls=0)

        sys.addaudithook(_sandbox_audit_hook)

        if enable_arc:
            arc_isolator.enable()
        try:
            result = func(**inputs)
            if sys.getsizeof(result) > 1024 * 1024 * 5:
                raise SandboxViolationError("Output size exceeds sandbox bound (5MB)")
        finally:
            if enable_arc:
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
    def run(func: Callable, inputs: dict[str, Any], timeout_seconds: int = 5, memory_mb: int = 512, trace_id: str = "default", enable_arc: bool = True) -> dict[str, Any]:
        manager = multiprocessing.Manager()
        return_dict = manager.dict()

        p = multiprocessing.Process(
            target=_sandboxed_execution_wrapper,
            args=(func, inputs, return_dict, trace_id, enable_arc, memory_mb, timeout_seconds)
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
    @staticmethod
    def verify_freeze_invariants(original_trace: list, replay_trace: list, intervened_component_id: str):
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

            if hashlib.sha256(orig_out).hexdigest() != hashlib.sha256(replay_out).hexdigest():
                raise InvariantViolationError(
                    f"Freeze invariant violated! Component {span_id} output changed during replay despite not being intervened."
                )
