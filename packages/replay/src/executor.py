"""
DriftGuard-X v2 — Isolated Replay Executor
Abstracts execution between local multiprocess sandboxes and production container boundaries.
"""

import asyncio
import contextlib
import json
import os
import re
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import cloudpickle
from pydantic import BaseModel

from packages.replay.src.sandbox import SandboxedWorker


class ReplayStateManifest(BaseModel):
    executor_type: str
    image_digest: str | None = None
    execution_time_seconds: float
    memory_used_bytes: int | None = None


class ReplayResult(BaseModel):
    payload: Any
    error: str | None = None
    manifest: ReplayStateManifest


class ReplayExecutor(ABC):
    @abstractmethod
    async def execute(
        self, func: Callable[..., Any], budget_seconds: float, **kwargs: Any
    ) -> ReplayResult:
        pass


class LocalDevExecutor(ReplayExecutor):
    """
    Executes replays using the existing local multiprocessing SandboxedWorker.
    Suitable for unit tests and local demo mode.
    """

    async def execute(
        self, func: Callable[..., Any], budget_seconds: float, **kwargs: Any
    ) -> ReplayResult:
        start_time = time.monotonic()

        try:
            # Wrap the blocking SandboxedWorker call in a thread
            result = await asyncio.to_thread(
                SandboxedWorker.run,
                func,
                kwargs,
                timeout_seconds=int(budget_seconds),
                trace_id="local_replay",
                enable_arc=False,
            )
            error = None
        except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
            result = None
            error = str(e)

        execution_time = time.monotonic() - start_time

        return ReplayResult(
            payload=result,
            error=error,
            manifest=ReplayStateManifest(
                executor_type="LocalDevExecutor",
                execution_time_seconds=execution_time,
                memory_used_bytes=None,
            ),
        )


class ContainerReplayExecutor(ReplayExecutor):
    """
    Production-oriented replay executor enforcing hard sandboxing using Docker.

    The image must be supplied by immutable registry digest. The executor never
    builds an image or resolves a mutable tag at runtime. Container output crosses
    the trust boundary as bounded JSON, never pickle/cloudpickle.
    """

    _DIGEST_PINNED_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")

    def __init__(self, image: str | None = None):
        resolved_image = image or os.environ.get("DGX_REPLAY_IMAGE", "")
        if not self._DIGEST_PINNED_IMAGE.fullmatch(resolved_image):
            raise ValueError(
                "DGX_REPLAY_IMAGE must be a registry image pinned by @sha256:<64 hex chars>"
            )
        self.image = resolved_image
        self.image_digest = resolved_image.rsplit("@", 1)[1]
        try:
            import docker

            self.client = docker.from_env()
            self.image_info = self.client.images.get(self.image)
        except ImportError:
            self.client = None

    async def execute(
        self, func: Callable[..., Any], budget_seconds: float, **kwargs: Any
    ) -> ReplayResult:
        if not self.client:
            raise RuntimeError("Docker SDK not installed or daemon unavailable.")

        MAX_REQUEST_SIZE_BYTES = 5 * 1024 * 1024

        # Serialize the function and arguments
        payload_data = cloudpickle.dumps((func, kwargs))
        if len(payload_data) > MAX_REQUEST_SIZE_BYTES:
            return ReplayResult(
                payload=None,
                error="Payload exceeds 5MB limit",
                manifest=ReplayStateManifest(
                    executor_type="ContainerReplayExecutor",
                    image_digest=self.image_digest,
                    execution_time_seconds=0,
                ),
            )

        # Create a temporary directory to share with the container
        temp_dir = tempfile.mkdtemp(prefix="driftguard_sandbox_")
        if os.name == "posix":
            # The digest-pinned image runs as uid 10001 and needs access only to
            # this per-replay exchange directory.
            os.chmod(temp_dir, 0o700)
        payload_path = os.path.join(temp_dir, "payload.pkl")
        result_path = os.path.join(temp_dir, "result.json")

        with open(payload_path, "wb") as f:
            f.write(payload_data)

        # The request contains trusted callable code and only travels into the
        # sandbox. The result travels back to the parent as bounded JSON.
        runner_script = """
import sys
import json

import cloudpickle

MAX_OUTPUT_BYTES = 10 * 1024 * 1024

def write_result(value):
    encoder = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    emitted = 0
    with open('/sandbox/result.json', 'w', encoding='utf-8') as output:
        for chunk in encoder.iterencode(value):
            emitted += len(chunk.encode('utf-8'))
            if emitted > MAX_OUTPUT_BYTES:
                raise RuntimeError("Response payload exceeds 10MB limit.")
            output.write(chunk)

def main():
    try:
        with open('/sandbox/payload.pkl', 'rb') as f:
            func, kwargs = cloudpickle.load(f)

        # Add DriftGuard-X to python path
        sys.path.insert(0, '/app')

        result = func(**kwargs)
        write_result({"status": "success", "payload": result})

    except BaseException as e:
        try:
            write_result({"status": "error", "error": f"{type(e).__name__}: {e}"})
        except BaseException:
            pass

if __name__ == '__main__':
    main()
"""
        script_path = os.path.join(temp_dir, "runner.py")
        with open(script_path, "w") as f:
            f.write(runner_script)

        container = None
        start_time = time.monotonic()
        error_msg = None

        try:
            # Only the per-replay exchange directory crosses the host boundary.
            # Application code and the frozen environment come from the pinned
            # image; the host repository is never mounted into the container.
            volumes = {temp_dir: {"bind": "/sandbox", "mode": "rw"}}

            # Spin up the container with hard boundaries
            container = self.client.containers.run(
                self.image,
                command=["python", "/sandbox/runner.py"],
                volumes=volumes,
                working_dir="/app",
                network_mode="none",  # Default deny network
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="128m",  # Memory cap
                nano_cpus=1000000000,  # 1 CPU core
                pids_limit=10,  # Prevent fork bombs
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},  # nosec B108: Storage limit
                detach=True,
                remove=False,
            )

            # Wait for it to finish asynchronously
            # We poll the container state since docker-py .wait() is blocking
            poll_interval = 0.1
            while True:
                container.reload()
                if container.status == "exited":
                    break

                if time.monotonic() - start_time > budget_seconds:
                    container.kill()
                    error_msg = f"TimeoutError: Exceeded {budget_seconds} seconds"
                    break

                await asyncio.sleep(poll_interval)

            # If not timed out, check results
            if not error_msg:
                # Get max memory used if possible
                try:
                    stats = container.stats(stream=False)
                    max_mem = stats.get("memory_stats", {}).get("max_usage")
                except (ValueError, RuntimeError, KeyError, TypeError, OSError):
                    max_mem = None
            else:
                max_mem = None

        except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
            error_msg = f"ContainerError: {e!s}"
            max_mem = None
        finally:
            if container:
                try:
                    container.stop(timeout=1)
                    container.remove(force=True)
                except (ValueError, RuntimeError, KeyError, TypeError, OSError):
                    pass

        execution_time = time.monotonic() - start_time

        # Load bounded JSON from the mount. Never deserialize container-controlled
        # pickle/cloudpickle in the parent process.
        result_payload = None
        if not error_msg:
            if os.path.exists(result_path):
                try:
                    max_response_bytes = 10 * 1024 * 1024
                    if os.path.getsize(result_path) > max_response_bytes:
                        raise RuntimeError("Response payload exceeds 10MB limit")
                    with open(result_path, "rb") as f:
                        encoded_result = f.read(max_response_bytes + 1)
                    if len(encoded_result) > max_response_bytes:
                        raise RuntimeError("Response payload exceeds 10MB limit")
                    res = json.loads(encoded_result)
                    if res["status"] == "success":
                        result_payload = res["payload"]
                    else:
                        error_msg = res["error"]
                except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
                    error_msg = f"Failed to decode bounded result: {e!s}"
            else:
                error_msg = "No result file found. Container may have crashed."

        # Cleanup temp dir (ignoring errors if files are locked)
        import shutil

        with contextlib.suppress(ValueError, RuntimeError, KeyError, TypeError, OSError):
            shutil.rmtree(temp_dir, ignore_errors=True)

        return ReplayResult(
            payload=result_payload,
            error=error_msg,
            manifest=ReplayStateManifest(
                executor_type="ContainerReplayExecutor",
                image_digest=self.image_digest,
                execution_time_seconds=execution_time,
                memory_used_bytes=max_mem,
            ),
        )
