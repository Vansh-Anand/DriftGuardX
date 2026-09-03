"""
DriftGuard-X v2 — Sandboxed Do-Operator Replay
Update 14: Atomic execution budget and multiprocessing OS limits.
PRIVATE — All Rights Reserved.
"""

import contextlib
import hashlib
import json
import multiprocessing
import sys
import threading
import time
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

    def __init__(
        self, max_memory_mb: int = 512, max_cpu_seconds: int = 10, max_network_calls: int = 0
    ):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_seconds = max_cpu_seconds
        self.max_network_calls = max_network_calls
        self._lock = threading.Lock()
        self.network_calls_used = 0

    def reserve_network_call(self) -> None:
        with self._lock:
            if self.network_calls_used >= self.max_network_calls:
                raise ExecutionBudgetExceeded(
                    f"Network call budget exceeded ({self.max_network_calls})."
                )
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


def _sandbox_audit_hook(event: str, args: tuple[Any, ...]) -> None:
    trace_id = getattr(sandbox_local, "trace_id", "unknown_trace")
    if not hasattr(sandbox_local, "staged_actions"):
        sandbox_local.staged_actions = []
    budget = getattr(sandbox_local, "budget", None)
    policy = getattr(sandbox_local, "policy", SandboxPolicy())

    if event.startswith("socket."):
        if not policy.allow_network:
            sandbox_local.staged_actions.append(
                {
                    "trace_id": trace_id,
                    "type": "NETWORK_CALL",
                    "payload": {"event": event, "args": str(args)},
                }
            )
            raise SandboxViolationError(
                f"Network access staged and blocked in sandbox: {event} {args}"
            )
        if budget:
            budget.reserve_network_call()

    if event == "open":
        filename, mode, *rest = args
        if isinstance(mode, str):
            if any(m in mode for m in ("w", "a", "x", "+")):
                if not _is_path_within(str(filename), policy.allowed_write_roots):
                    sandbox_local.staged_actions.append(
                        {
                            "trace_id": trace_id,
                            "type": "FILE_WRITE",
                            "payload": {"filename": str(filename), "mode": mode},
                        }
                    )
                    raise SandboxViolationError(
                        f"File write staged and blocked in sandbox: {filename}"
                    )
            elif "r" in mode:
                if not _is_path_within(str(filename), policy.allowed_read_roots):
                    raise SandboxViolationError(
                        f"File read outside allowed directory blocked in sandbox: {filename}"
                    )

    if event in ("os.fork", "os.forkpty", "os.spawn", "os.exec", "os.posix_spawn"):
        sandbox_local.staged_actions.append(
            {"trace_id": trace_id, "type": "PROCESS_SPAWN", "payload": {"event": event}}
        )
        raise SandboxViolationError(f"Process spawning staged and blocked in sandbox: {event}")

    if event.startswith("subprocess.") or event == "os.system":
        if not policy.allow_subprocess:
            sandbox_local.staged_actions.append(
                {
                    "trace_id": trace_id,
                    "type": "SHELL_EXEC",
                    "payload": {"event": event, "command": str(args)},
                }
            )
            raise SandboxViolationError(f"Shell execution staged and blocked in sandbox: {event}")

    if event == "os.kill":
        raise SandboxViolationError("Process signaling (os.kill) blocked in sandbox.")


def _apply_os_limits(memory_mb: int, cpu_seconds: int) -> None:
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
        print(
            "WARNING: OS resource limits (RLIMIT) unavailable on this platform. Falling back to multiprocessing timeouts."
        )


def _send_bounded_json(connection: Any, value: Any, max_output_bytes: int) -> None:
    """Stream JSON frames without ever allocating a full serialized payload."""
    encoder = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    emitted = 0
    for text_chunk in encoder.iterencode(value):
        encoded = text_chunk.encode("utf-8")
        for offset in range(0, len(encoded), 64 * 1024):
            chunk = encoded[offset : offset + 64 * 1024]
            emitted += len(chunk)
            if emitted > max_output_bytes:
                raise SandboxViolationError(
                    f"Output size exceeds sandbox bound ({max_output_bytes} bytes)"
                )
            connection.send_bytes(b"D" + chunk)
    connection.send_bytes(b"E")


def _sandboxed_execution_wrapper(
    func: Callable[..., Any],
    inputs: dict[str, Any],
    connection: Any,
    trace_id: str,
    enable_arc: bool = True,
    memory_mb: int = 512,
    cpu_seconds: int = 10,
    sandbox_work_dir: str = "",
    max_output_bytes: int = 5 * 1024 * 1024,
) -> None:
    try:
        from packages.replay.src.arc_isolator import arc_isolator

        _apply_os_limits(memory_mb, cpu_seconds)

        sandbox_local.trace_id = trace_id
        sandbox_local.staged_actions = []
        sandbox_local.budget = AtomicExecutionBudget(
            max_memory_mb=memory_mb, max_cpu_seconds=cpu_seconds, max_network_calls=0
        )

        policy = SandboxPolicy(
            max_output_bytes=max_output_bytes,
            max_memory_mb=memory_mb,
            max_cpu_seconds=cpu_seconds,
            allowed_read_roots=[sandbox_work_dir] if sandbox_work_dir else [],
            allowed_write_roots=[sandbox_work_dir] if sandbox_work_dir else [],
        )
        sandbox_local.policy = policy

        sys.addaudithook(_sandbox_audit_hook)

        if enable_arc:
            arc_isolator.enable()
        try:
            result = func(**inputs)
        finally:
            if enable_arc:
                arc_isolator.disable()

        _send_bounded_json(
            connection,
            {"result": result, "staged_actions": sandbox_local.staged_actions},
            policy.max_output_bytes,
        )
    except (
        SandboxViolationError,
        ExecutionBudgetExceeded,
        ValueError,
        TypeError,
        RuntimeError,
        ImportError,
    ) as e:
        error = json.dumps(
            {
                "error": str(e),
                "staged_actions": getattr(sandbox_local, "staged_actions", []),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with contextlib.suppress(BrokenPipeError, EOFError, OSError):
            connection.send_bytes(b"X" + error[: 64 * 1024])
    finally:
        connection.close()


class SandboxedWorker:
    """
    Executes a function in a tightly restricted multiprocessing boundary.
    """

    @staticmethod
    def run(
        func: Callable[..., Any],
        inputs: dict[str, Any],
        timeout_seconds: int = 5,
        memory_mb: int = 512,
        trace_id: str = "default",
        enable_arc: bool = True,
        sandbox_work_dir: str = "",
        max_output_bytes: int = 5 * 1024 * 1024,
    ) -> Any:
        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=False)
        p = context.Process(
            target=_sandboxed_execution_wrapper,
            args=(
                func,
                inputs,
                child_connection,
                trace_id,
                enable_arc,
                memory_mb,
                timeout_seconds,
                sandbox_work_dir,
                max_output_bytes,
            ),
        )
        p.start()
        child_connection.close()
        deadline = time.monotonic() + timeout_seconds
        payload = bytearray()
        envelope: dict[str, Any] | None = None
        try:
            try:
                import psutil
            except ImportError:
                monitored_process = None
            else:
                try:
                    monitored_process = psutil.Process(p.pid)
                except psutil.Error:
                    monitored_process = None

            while time.monotonic() < deadline:
                if monitored_process is not None:
                    try:
                        if monitored_process.memory_info().rss > memory_mb * 1024 * 1024:
                            raise MemoryError(
                                f"Sandbox exceeded hard memory limit ({memory_mb} MiB)"
                            )
                    except psutil.NoSuchProcess:
                        monitored_process = None

                if parent_connection.poll(0.02):
                    frame = parent_connection.recv_bytes(maxlength=64 * 1024 + 1)
                    frame_type, frame_payload = frame[:1], frame[1:]
                    if frame_type == b"D":
                        if len(payload) + len(frame_payload) > max_output_bytes:
                            raise MemoryError("Sandbox output exceeded resource bounds")
                        payload.extend(frame_payload)
                    elif frame_type == b"E":
                        decoded = json.loads(payload)
                        if not isinstance(decoded, dict):
                            raise RuntimeError("Sandbox returned an invalid envelope")
                        envelope = decoded
                        break
                    elif frame_type == b"X":
                        error_envelope = json.loads(frame_payload)
                        envelope = error_envelope
                        break
                    else:
                        raise RuntimeError("Sandbox emitted an invalid output frame")
                elif not p.is_alive():
                    raise RuntimeError(
                        f"Sandbox process exited without a result (exit code {p.exitcode})"
                    )
            else:
                raise TimeoutError("Sandboxed execution timed out.")
        finally:
            parent_connection.close()
            if p.is_alive():
                p.terminate()
                p.join(timeout=2.0)
                if p.is_alive():
                    p.kill()
            p.join(timeout=2.0)

        if envelope is None:
            raise RuntimeError("Sandbox returned no result")

        from packages.replay.src.vti_coordinator import vti_coordinator

        for action in envelope.get("staged_actions", []):
            vti_coordinator.stage_action(action["trace_id"], action["type"], action["payload"])

        if "error" in envelope:
            raise RuntimeError(f"Sandbox error: {envelope['error']}")

        return envelope.get("result")


class ReplayEngineWithInvariants:
    @staticmethod
    def verify_freeze_invariants(
        original_trace: list[dict[str, Any]],
        replay_trace: list[dict[str, Any]],
        intervened_component_id: str,
    ) -> None:
        orig_map = {s["span_id"]: s for s in original_trace}
        replay_map = {s["span_id"]: s for s in replay_trace}

        for span_id, orig_span in orig_map.items():
            if orig_span.get("component_type") == intervened_component_id:
                continue

            if span_id not in replay_map:
                continue

            replay_span = replay_map[span_id]

            orig_out = json.dumps(orig_span.get("output", {}), sort_keys=True).encode()
            replay_out = json.dumps(replay_span.get("output", {}), sort_keys=True).encode()

            if hashlib.sha256(orig_out).hexdigest() != hashlib.sha256(replay_out).hexdigest():
                raise InvariantViolationError(
                    f"Freeze invariant violated! Component {span_id} output changed during replay despite not being intervened."
                )
