"""
DriftGuard-X v2 — Sandboxed Do-Operator Replay
Update 14: Atomic execution budget and multiprocessing OS limits.
PRIVATE — All Rights Reserved.
"""
import hashlib
import json
import multiprocessing
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SandboxPolicy:
    """
    Strict sandbox policy dictating isolation boundaries.
    
    THREAT MODEL:
    - This sandbox provides Restricted Subprocess isolation.
    - It is NOT a perfectly secure, zero-trust container.
    - It uses Python audit hooks (defense-in-depth) and OS RLIMITs where available.
    - It DOES NOT protect against:
        - Native C-extension memory escapes
        - Kernel-level vulnerabilities
        - Pre-existing native backdoors in allowed modules
    """
    allowed_read_roots: list[str] = field(default_factory=list)
    allowed_write_roots: list[str] = field(default_factory=list)
    max_output_bytes: int = 5 * 1024 * 1024  # 5MB
    max_memory_mb: int = 512
    max_cpu_seconds: int = 10
    max_wall_seconds: int = 15
    max_network_calls: int = 0
    allow_subprocess: bool = False
    allow_fork: bool = False
    allow_exec: bool = False
    allow_network: bool = False
    environment_allowlist: list[str] = field(default_factory=list)
    filesystem_mode: str = "restricted"

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

def _is_path_within(candidate: str, allowed_roots: list[str]) -> bool:
    try:
        cand_path = Path(candidate).resolve(strict=False)
        for root in allowed_roots:
            root_path = Path(root).resolve(strict=False)
            if cand_path.is_relative_to(root_path):
                return True
        return False
    except (ValueError, RuntimeError, OSError):
        return False

def _sandbox_audit_hook(event: str, args: tuple):
    trace_id = getattr(sandbox_local, "trace_id", "unknown_trace")
    if not hasattr(sandbox_local, "staged_actions"):
        sandbox_local.staged_actions = []
    budget = getattr(sandbox_local, "budget", None)
    policy = getattr(sandbox_local, "policy", SandboxPolicy())

    if event.startswith("socket."):
        if not policy.allow_network:
            sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "NETWORK_CALL", "payload": {"event": event, "args": str(args)}})
            raise SandboxViolationError(f"Network access staged and blocked in sandbox: {event} {args}")
        if budget:
            budget.reserve_network_call()

    if event == "open":
        filename, mode, *rest = args
        if isinstance(mode, str):
            if any(m in mode for m in ('w', 'a', 'x', '+')):
                if not _is_path_within(str(filename), policy.allowed_write_roots):
                    sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "FILE_WRITE", "payload": {"filename": str(filename), "mode": mode}})
                    raise SandboxViolationError(f"File write staged and blocked in sandbox: {filename}")
            elif 'r' in mode:
                if not _is_path_within(str(filename), policy.allowed_read_roots):
                    raise SandboxViolationError(f"File read outside allowed directory blocked in sandbox: {filename}")

    if event in ("os.fork", "os.forkpty", "os.spawn", "os.exec", "os.posix_spawn"):
        sandbox_local.staged_actions.append({"trace_id": trace_id, "type": "PROCESS_SPAWN", "payload": {"event": event}})
        raise SandboxViolationError(f"Process spawning staged and blocked in sandbox: {event}")

    if event.startswith("subprocess.") or event == "os.system":
        if not policy.allow_subprocess:
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

def _sandboxed_execution_wrapper(func: Callable, inputs: dict[str, Any], return_dict: dict, trace_id: str, enable_arc: bool = True, memory_mb: int = 512, cpu_seconds: int = 10, sandbox_work_dir: str = ""):
    try:
        from packages.replay.src.arc_isolator import arc_isolator

        _apply_os_limits(memory_mb, cpu_seconds)

        sandbox_local.trace_id = trace_id
        sandbox_local.staged_actions = []
        sandbox_local.budget = AtomicExecutionBudget(max_memory_mb=memory_mb, max_cpu_seconds=cpu_seconds, max_network_calls=0)

        policy = SandboxPolicy(
            max_memory_mb=memory_mb,
            max_cpu_seconds=cpu_seconds,
            allowed_read_roots=[sandbox_work_dir] if sandbox_work_dir else [],
            allowed_write_roots=[sandbox_work_dir] if sandbox_work_dir else []
        )
        sandbox_local.policy = policy

        sys.addaudithook(_sandbox_audit_hook)

        if enable_arc:
            arc_isolator.enable()
        try:
            result = func(**inputs)
            # Use JSON serialization length for robust size bound
            try:
                serialized = json.dumps(result)
                if len(serialized) > policy.max_output_bytes:
                    raise SandboxViolationError(f"Output size exceeds sandbox bound ({policy.max_output_bytes} bytes)")
            except (TypeError, ValueError):
                # Fallback to recursive compute
                def deep_size(obj, seen=None):
                    if seen is None:
                        seen = set()
                    obj_id = id(obj)
                    if obj_id in seen:
                        return 0
                    seen.add(obj_id)
                    size = sys.getsizeof(obj)
                    if isinstance(obj, dict):
                        size += sum(deep_size(k, seen) + deep_size(v, seen) for k, v in obj.items())
                    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                        size += sum(deep_size(i, seen) for i in obj)
                    return size

                if deep_size(result) > policy.max_output_bytes:
                    raise SandboxViolationError(f"Output size exceeds sandbox bound ({policy.max_output_bytes} bytes)")
        finally:
            if enable_arc:
                arc_isolator.disable()

        return_dict['result'] = result
        return_dict['staged_actions'] = sandbox_local.staged_actions
    except (SandboxViolationError, ExecutionBudgetExceeded, ValueError, TypeError, RuntimeError, ImportError) as e:
        return_dict['error'] = str(e)
        return_dict['staged_actions'] = getattr(sandbox_local, "staged_actions", [])

class SandboxedWorker:
    """
    Executes a function in a tightly restricted multiprocessing boundary.
    """
    @staticmethod
    def run(func: Callable, inputs: dict[str, Any], timeout_seconds: int = 5, memory_mb: int = 512, trace_id: str = "default", enable_arc: bool = True, sandbox_work_dir: str = "") -> dict[str, Any]:
        manager = multiprocessing.Manager()
        return_dict = manager.dict()

        p = multiprocessing.Process(
            target=_sandboxed_execution_wrapper,
            args=(func, inputs, return_dict, trace_id, enable_arc, memory_mb, timeout_seconds, sandbox_work_dir)
        )
        p.start()
        p.join(timeout=timeout_seconds)

        if p.is_alive():
            p.terminate()
            p.join(timeout=2.0)
            if p.is_alive():
                p.kill()
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
